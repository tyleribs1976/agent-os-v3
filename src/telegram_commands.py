import os
import pyotp
import logging
import traceback
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from ai_suggester import generate_ai_suggestions

@contextmanager
def get_db_connection():
    """Get PostgreSQL database connection with proper row factory"""
    db_url = os.getenv('DATABASE_URL', 'postgresql://localhost:5432/agent_os_v3')
    conn = psycopg2.connect(db_url)
    try:
        yield conn
    finally:
        conn.close()

def query_one(sql, params=None):
    """Execute query and return single row as dict"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(sql, params or [])
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logging.error(f"query_one error: {e}")
        return None

def query_all(sql, params=None):
    """Execute query and return all rows as list of dicts"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(sql, params or [])
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

def execute_sql(sql, params=None):
    """Execute INSERT/UPDATE/DELETE and return affected row count or inserted id"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(sql, params or [])
            conn.commit()
            try:
                return cursor.fetchone()
            except:
                return {'affected': cursor.rowcount}


def progress_bar(completed, total, width=10):
    """Generate a text progress bar"""
    if total == 0:
        return "░" * width
    filled = int((completed / total) * width)
    return "█" * filled + "░" * (width - filled)


def phase_emoji(completed, total, failed, halted):
    """Get appropriate emoji for phase status"""
    if completed == total and total > 0:
        return "✅"
    if halted and halted > 0:
        return "🛑"
    if failed and failed > 0:
        return "⚠️"
    if completed and completed > 0:
        return "🔄"
    return "⏳"


STATUS_EMOJI = {
    'complete': '✅', 'failed': '❌', 'running': '🔄',
    'in_progress': '🔄', 'queued': '📋', 'pending': '⏳', 'halted': '🛑',
    'archived': '🗑️'
}

# Failure categories and remediation strategies
FAILURE_CATEGORIES = {
    'branch_exists': {
        'patterns': ['branch named', 'already exists'],
        'category': 'environment',
        'remediation': 'cleanup_branch',
        'description': 'Git branch already exists from previous attempt',
        'auto_fix': True
    },
    'undefined_variable': {
        'patterns': ['is not defined', 'NameError'],
        'category': 'code_bug',
        'remediation': 'report_bug',
        'description': 'Code bug in Agent-OS executor',
        'auto_fix': False
    },
    'low_confidence': {
        'patterns': ['confidence score', 'below threshold'],
        'category': 'task_ambiguity', 
        'remediation': 'refine_task',
        'description': 'Task needs more specific requirements',
        'auto_fix': False
    },
    'api_error': {
        'patterns': ['API', 'rate limit', '401', '403', '500'],
        'category': 'external',
        'remediation': 'wait_retry',
        'description': 'External API issue',
        'auto_fix': True
    },
    'merge_conflict': {
        'patterns': ['merge conflict', 'CONFLICT'],
        'category': 'git',
        'remediation': 'manual_resolve',
        'description': 'Git merge conflict needs manual resolution',
        'auto_fix': False
    },
    'timeout': {
        'patterns': ['timeout', 'timed out'],
        'category': 'performance',
        'remediation': 'decompose_task',
        'description': 'Task took too long - may need to be split',
        'auto_fix': False
    }
}

def categorize_failure(error_text: str) -> dict:
    """Categorize a failure based on error patterns"""
    if not error_text:
        return {'category': 'unknown', 'remediation': 'manual_review', 'description': 'No error details available'}
    
    error_lower = error_text.lower()
    for key, info in FAILURE_CATEGORIES.items():
        if any(p.lower() in error_lower for p in info['patterns']):
            return {
                'type': key,
                'category': info['category'],
                'remediation': info['remediation'],
                'description': info['description'],
                'auto_fix': info.get('auto_fix', False)
            }
    
    return {'type': 'unknown', 'category': 'unknown', 'remediation': 'manual_review', 'description': 'Unrecognized error pattern'}


def get_task_failure_history(task_id: str) -> list:
    """Get all failure checkpoints for a task"""
    return query_all("""
        SELECT c.id, c.phase, c.step_name, c.status, c.error_details, c.created_at
        FROM checkpoints c
        WHERE c.task_id = %s AND c.status = 'failed'
        ORDER BY c.created_at DESC
        LIMIT 10
    """, [task_id]) or []


def get_related_tasks(title: str) -> list:
    """Find related tasks (retries of same task)"""
    # Remove "Retry: " prefix variations
    base_title = title.replace('Retry: ', '').replace('Retry:', '').strip()
    return query_all("""
        SELECT id, title, status, current_phase, error_message, created_at
        FROM tasks
        WHERE title LIKE %s OR title LIKE %s
        ORDER BY created_at DESC
        LIMIT 10
    """, [f"%{base_title}%", f"%Retry%{base_title}%"]) or []


def get_base_task_title(title: str) -> str:
    """Extract base task title without Retry: prefix"""
    return title.replace('Retry: ', '').replace('Retry:', '').strip()


def get_unique_failed_tasks() -> list:
    """Get unique failed/halted tasks, consolidating retries"""
    # Get all failed/halted tasks
    all_failed = query_all("""
        SELECT id, title, status, current_phase, error_message, description, updated_at, created_at
        FROM tasks
        WHERE status IN ('failed', 'halted')
        ORDER BY updated_at DESC
    """) or []
    
    # Group by base title, keep the most recent one
    seen_titles = {}
    unique_tasks = []
    
    for task in all_failed:
        base_title = get_base_task_title(task.get('title', ''))
        if base_title not in seen_titles:
            seen_titles[base_title] = task
            # Count how many related tasks exist
            related_count = sum(1 for t in all_failed if get_base_task_title(t.get('title', '')) == base_title)
            task['retry_count'] = related_count - 1
            unique_tasks.append(task)
    
    return unique_tasks


def cleanup_duplicate_tasks() -> dict:
    """Archive duplicate retry tasks, keeping only the original or most recent"""
    # Get all failed/halted tasks grouped by base title
    all_failed = query_all("""
        SELECT id, title, status, current_phase, created_at
        FROM tasks
        WHERE status IN ('failed', 'halted')
        ORDER BY title, created_at ASC
    """) or []
    
    # Group by base title
    groups = {}
    for task in all_failed:
        base_title = get_base_task_title(task.get('title', ''))
        if base_title not in groups:
            groups[base_title] = []
        groups[base_title].append(task)
    
    archived_count = 0
    kept_tasks = []
    
    for base_title, tasks in groups.items():
        if len(tasks) <= 1:
            kept_tasks.append(tasks[0] if tasks else None)
            continue
        
        # Keep the original (non-Retry) if it exists, otherwise keep the first one
        original = None
        retries = []
        for t in tasks:
            if not t.get('title', '').startswith('Retry:'):
                original = t
            else:
                retries.append(t)
        
        # Keep original or first retry
        keeper = original or tasks[0]
        kept_tasks.append(keeper)
        
        # Archive all others
        for t in tasks:
            if t['id'] != keeper['id']:
                execute_sql("""
                    UPDATE tasks 
                    SET status = 'archived', 
                        error_message = COALESCE(error_message, '') || ' [Auto-archived: duplicate of ' || %s || ']',
                        updated_at = NOW()
                    WHERE id = %s
                """, [str(keeper['id'])[:8], t['id']])
                archived_count += 1
    
    return {
        'archived': archived_count,
        'kept': len([t for t in kept_tasks if t]),
        'kept_tasks': [t for t in kept_tasks if t]
    }

PHASE_ORDER = ['preparation', 'drafting', 'verification', 'execution', 'confirmation']
PHASE_DISPLAY = {
    'preparation': 'Prep',
    'drafting': 'Draft', 
    'verification': 'Verify',
    'execution': 'Execute',
    'confirmation': 'PR'
}

def render_task_progress(task: dict) -> str:
    """Render visual task progress with pipeline and progress bar"""
    status = task.get('status', 'unknown')
    current_phase = task.get('current_phase', 'preparation')
    title = task.get('title', 'Untitled')
    task_id = str(task.get('id', ''))
    
    # Status header
    status_emoji = STATUS_EMOJI.get(status, '❓')
    if status == 'complete':
        header = "✅ Task Complete"
    elif status == 'failed':
        header = "❌ Task Failed"
    elif status == 'running' or status == 'in_progress':
        header = "🔄 Task Running"
    elif status == 'halted':
        header = "🛑 Task Halted"
    elif status == 'queued':
        header = "📋 Task Queued"
    else:
        header = f"{status_emoji} Task: {status.title()}"
    
    msg = f"{header}\n\n"
    msg += f"📌 {title}\n"
    msg += f"🆔 {task_id[:8]}...{task_id[-4:]}\n\n"
    
    # Progress bar
    try:
        phase_idx = PHASE_ORDER.index(current_phase) if current_phase in PHASE_ORDER else 0
    except ValueError:
        phase_idx = 0
    
    if status == 'complete':
        phase_idx = len(PHASE_ORDER)
        pct = 100
    elif status == 'failed':
        pct = int((phase_idx / len(PHASE_ORDER)) * 100)
    else:
        pct = int(((phase_idx + 0.5) / len(PHASE_ORDER)) * 100)
    
    # Visual progress bar (20 chars)
    filled = int(pct / 5)
    bar = "▓" * filled + "░" * (20 - filled)
    msg += f"{bar} {pct}%\n\n"
    
    # Phase pipeline
    pipeline_parts = []
    for i, phase in enumerate(PHASE_ORDER):
        display = PHASE_DISPLAY.get(phase, phase)
        if status == 'complete' or i < phase_idx:
            pipeline_parts.append(f"✅ {display}")
        elif i == phase_idx and status in ('running', 'in_progress', 'failed', 'halted'):
            if status == 'failed':
                pipeline_parts.append(f"❌ {display}")
            elif status == 'halted':
                pipeline_parts.append(f"🛑 {display}")
            else:
                pipeline_parts.append(f"▶️ {display}")
        else:
            pipeline_parts.append(f"⬜ {display}")
    
    msg += " → ".join(pipeline_parts) + "\n\n"
    
    # Time if available
    if task.get('created_at') and task.get('updated_at'):
        try:
            created = task['created_at']
            updated = task['updated_at']
            if hasattr(created, 'timestamp') and hasattr(updated, 'timestamp'):
                duration = updated - created
                mins = int(duration.total_seconds() // 60)
                secs = int(duration.total_seconds() % 60)
                msg += f"⏱️ Duration: {mins}m {secs}s\n\n"
        except:
            pass
    
    # Project and milestone info
    if task.get('project_name'):
        msg += f"📁 {task['project_name']}\n"
    if task.get('milestone_name'):
        msg += f"🗺️ Phase {task.get('phase_number', '?')}: {task['milestone_name']}\n"
    msg += f"🔧 {task.get('task_type', 'implementation')} | P{task.get('priority', 5)}\n"
    
    # Error summary if failed
    if status == 'failed' and task.get('error_message'):
        err = task.get('error_message', '')
        if len(err) > 100:
            err = err[:97] + "..."
        msg += f"\n📋 Error: {err}"
    
    # Description
    desc = task.get('description', '')
    if desc:
        if len(desc) > 150:
            desc = desc[:147] + "..."
        msg += f"\n\n📝 {desc}"
    
    return msg


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available commands"""
    help_text = """🤖 Agent-OS v3 Commands:

📊 Status & Overview
/help - Show this message
/status - System status overview
/roadmap - Milestones with progress

📋 Task Management  
/tasks - List recent tasks
/queue - Show queued tasks
/run - View & run queued tasks
/run <id> - View specific task

🔧 Failure Management
/analyze - Analyze failed tasks
/analyze <id> - Diagnose specific task
/refine <id> <desc> - Update task description

✨ Planning
/suggest - Show task suggestions
/suggest refresh - Fresh AI suggestions
/suggest refresh <notes> - AI suggestions with focus
/addphase - Add new milestone phase"""
    await update.message.reply_text(help_text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system status with active tasks and latest checkpoint"""
    try:
        # Get task counts by status
        status_counts = query_all("""
            SELECT status, COUNT(*) as count FROM tasks GROUP BY status ORDER BY count DESC
        """)
        
        # Get latest checkpoint
        latest_checkpoint = query_one("""
            SELECT phase, step_name, created_at, status 
            FROM checkpoints 
            ORDER BY global_sequence DESC 
            LIMIT 1
        """)
        
        if latest_checkpoint:
            phase = latest_checkpoint.get('phase', 'unknown')
            step = latest_checkpoint.get('step_name', '')
            checkpoint_info = f"Latest: {phase}"
            if step:
                checkpoint_info += f"/{step}"
            if latest_checkpoint.get('created_at'):
                checkpoint_info += f" @ {latest_checkpoint['created_at'].strftime('%H:%M')}"
        else:
            checkpoint_info = "No checkpoints"
        
        msg = "🤖 Agent-OS v3 Status\n\n📊 Tasks:\n"
        for sc in status_counts:
            emoji = STATUS_EMOJI.get(sc['status'], '❓')
            msg += f"  {emoji} {sc['status']}: {sc['count']}\n"
        msg += f"\n🏁 {checkpoint_info}"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        logging.error(f"Status command error: {e}")
        await update.message.reply_text(f"❌ Status error: {str(e)}")


async def roadmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show roadmap with milestones and clickable phases"""
    try:
        # Exclude archived tasks and "Retry:" duplicates from counts
        milestones = query_all("""
            SELECT 
                m.id, m.name, m.phase_number,
                COUNT(t.id) FILTER (WHERE t.status != 'archived' AND t.title NOT LIKE 'Retry:%%') as total_tasks,
                SUM(CASE WHEN t.status = 'complete' AND t.title NOT LIKE 'Retry:%%' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN t.status IN ('running', 'in_progress') AND t.title NOT LIKE 'Retry:%%' THEN 1 ELSE 0 END) as in_progress,
                SUM(CASE WHEN t.status = 'failed' AND t.title NOT LIKE 'Retry:%%' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN t.status = 'halted' AND t.title NOT LIKE 'Retry:%%' THEN 1 ELSE 0 END) as halted
            FROM milestones m
            LEFT JOIN tasks t ON t.milestone_id = m.id
            GROUP BY m.id, m.name, m.phase_number
            ORDER BY m.phase_number
        """)
        
        unassigned = query_one("""
            SELECT COUNT(*) as total,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM tasks 
            WHERE milestone_id IS NULL 
              AND status != 'archived'
              AND title NOT LIKE 'Retry:%%'
        """)
        
        msg = "🗺️ Agent-OS v3 Roadmap\n\n"
        keyboard = []
        
        for m in milestones:
            total = m.get('total_tasks', 0) or 0
            completed = m.get('completed', 0) or 0
            failed = m.get('failed', 0) or 0
            halted = m.get('halted', 0) or 0
            in_prog = m.get('in_progress', 0) or 0
            
            pct = int((completed / total * 100)) if total > 0 else 0
            emoji = phase_emoji(completed, total, failed, halted)
            bar = progress_bar(completed, total)
            
            msg += f"{emoji} Phase {m['phase_number']}: {m['name']}\n"
            msg += f"   {bar} {pct}% ({completed}/{total})\n"
            
            # Show issues inline
            issues = []
            if in_prog > 0:
                issues.append(f"🔄{in_prog}")
            if failed > 0:
                issues.append(f"❌{failed}")
            if halted > 0:
                issues.append(f"🛑{halted}")
            if issues:
                msg += f"   {' '.join(issues)}\n"
            msg += "\n"
            
            # Add button for this phase
            btn_text = f"📂 Phase {m['phase_number']}: {m['name']}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"phase_{m['id']}")])
        
        # Summary
        total_tasks = sum(m.get('total_tasks', 0) or 0 for m in milestones)
        total_completed = sum(m.get('completed', 0) or 0 for m in milestones)
        overall_pct = int((total_completed / total_tasks * 100)) if total_tasks > 0 else 0
        
        msg += f"📊 Overall: {progress_bar(total_completed, total_tasks)} {overall_pct}%\n"
        
        # Unassigned button if any
        if unassigned and unassigned.get('total', 0) > 0:
            una_total = unassigned['total']
            una_failed = unassigned.get('failed', 0) or 0
            btn_text = f"📦 Unassigned ({una_total} tasks)"
            if una_failed > 0:
                btn_text += f" ❌{una_failed}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data="phase_unassigned")])
        
        # Add expand all button
        keyboard.append([InlineKeyboardButton("📋 Expand All Phases", callback_data="expand_all")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Roadmap command error: {e}")
        await update.message.reply_text(f"❌ Roadmap error: {str(e)}")


async def phase_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phase button clicks - show tasks in that phase"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data
        
        if data == "phase_unassigned":
            # Show unassigned tasks (exclude archived and Retry: duplicates)
            tasks = query_all("""
                SELECT id, title, status, priority
                FROM tasks 
                WHERE milestone_id IS NULL
                  AND status != 'archived'
                  AND title NOT LIKE 'Retry:%%'
                ORDER BY 
                    CASE status WHEN 'failed' THEN 1 WHEN 'running' THEN 2 ELSE 3 END,
                    priority DESC
                LIMIT 15
            """)
            msg = "📦 Unassigned Tasks:\n\n"
            
        elif data.startswith("phase_"):
            phase_id = int(data.replace("phase_", ""))
            
            # Get milestone info
            milestone = query_one("SELECT name, phase_number, description FROM milestones WHERE id = %s", [phase_id])
            if not milestone:
                await query.edit_message_text("❌ Phase not found")
                return
            
            # Exclude archived and Retry: duplicates
            tasks = query_all("""
                SELECT id, title, status, priority
                FROM tasks 
                WHERE milestone_id = %s
                  AND status != 'archived'
                  AND title NOT LIKE 'Retry:%%'
                ORDER BY 
                    CASE status WHEN 'failed' THEN 1 WHEN 'halted' THEN 2 WHEN 'running' THEN 3 WHEN 'queued' THEN 4 ELSE 5 END,
                    priority DESC
            """, [phase_id])
            
            msg = f"📂 Phase {milestone['phase_number']}: {milestone['name']}\n"
            if milestone.get('description'):
                msg += f"   {milestone['description']}\n"
            msg += "\n"
        
        else:
            await query.edit_message_text("❌ Unknown action")
            return
        
        if not tasks:
            msg += "No tasks in this phase."
        else:
            for t in tasks:
                emoji = STATUS_EMOJI.get(t.get('status', ''), '❓')
                title = t.get('title', 'Untitled')
                if len(title) > 35:
                    title = title[:32] + "..."
                priority = t.get('priority', 0)
                msg += f"{emoji} P{priority}: {title}\n"
        
        # Add back button
        keyboard = [[InlineKeyboardButton("← Back to Roadmap", callback_data="back_roadmap")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Phase callback error: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")


async def back_roadmap_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to roadmap button"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Exclude archived tasks and "Retry:" duplicates from counts
        milestones = query_all("""
            SELECT 
                m.id, m.name, m.phase_number,
                COUNT(t.id) FILTER (WHERE t.status != 'archived' AND t.title NOT LIKE 'Retry:%%') as total_tasks,
                SUM(CASE WHEN t.status = 'complete' AND t.title NOT LIKE 'Retry:%%' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN t.status IN ('running', 'in_progress') AND t.title NOT LIKE 'Retry:%%' THEN 1 ELSE 0 END) as in_progress,
                SUM(CASE WHEN t.status = 'failed' AND t.title NOT LIKE 'Retry:%%' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN t.status = 'halted' AND t.title NOT LIKE 'Retry:%%' THEN 1 ELSE 0 END) as halted
            FROM milestones m
            LEFT JOIN tasks t ON t.milestone_id = m.id
            GROUP BY m.id, m.name, m.phase_number
            ORDER BY m.phase_number
        """)
        
        unassigned = query_one("""
            SELECT COUNT(*) as total,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM tasks 
            WHERE milestone_id IS NULL 
              AND status != 'archived'
              AND title NOT LIKE 'Retry:%%'
        """)
        
        msg = "🗺️ Agent-OS v3 Roadmap\n\n"
        keyboard = []
        
        for m in milestones:
            total = m.get('total_tasks', 0) or 0
            completed = m.get('completed', 0) or 0
            failed = m.get('failed', 0) or 0
            halted = m.get('halted', 0) or 0
            in_prog = m.get('in_progress', 0) or 0
            
            pct = int((completed / total * 100)) if total > 0 else 0
            emoji = phase_emoji(completed, total, failed, halted)
            bar = progress_bar(completed, total)
            
            msg += f"{emoji} Phase {m['phase_number']}: {m['name']}\n"
            msg += f"   {bar} {pct}% ({completed}/{total})\n"
            
            issues = []
            if in_prog > 0:
                issues.append(f"🔄{in_prog}")
            if failed > 0:
                issues.append(f"❌{failed}")
            if halted > 0:
                issues.append(f"🛑{halted}")
            if issues:
                msg += f"   {' '.join(issues)}\n"
            msg += "\n"
            
            btn_text = f"📂 Phase {m['phase_number']}: {m['name']}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"phase_{m['id']}")])
        
        total_tasks = sum(m.get('total_tasks', 0) or 0 for m in milestones)
        total_completed = sum(m.get('completed', 0) or 0 for m in milestones)
        overall_pct = int((total_completed / total_tasks * 100)) if total_tasks > 0 else 0
        
        msg += f"📊 Overall: {progress_bar(total_completed, total_tasks)} {overall_pct}%\n"
        
        if unassigned and unassigned.get('total', 0) > 0:
            una_total = unassigned['total']
            una_failed = unassigned.get('failed', 0) or 0
            btn_text = f"📦 Unassigned ({una_total} tasks)"
            if una_failed > 0:
                btn_text += f" ❌{una_failed}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data="phase_unassigned")])
        
        # Add expand all button
        keyboard.append([InlineKeyboardButton("📋 Expand All Phases", callback_data="expand_all")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Back roadmap error: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")


async def expand_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle expand all phases button - show all tasks grouped by phase"""
    query = update.callback_query
    await query.answer()
    
    try:
        milestones = query_all("""
            SELECT m.id, m.name, m.phase_number, m.description
            FROM milestones m
            ORDER BY m.phase_number
        """)
        
        msg = "🗺️ Agent-OS v3 - All Tasks\n\n"
        
        for m in milestones:
            # Exclude archived tasks and "Retry:" duplicates
            tasks = query_all("""
                SELECT id, title, status, priority
                FROM tasks 
                WHERE milestone_id = %s
                  AND status != 'archived'
                  AND title NOT LIKE 'Retry:%%'
                ORDER BY 
                    CASE status WHEN 'failed' THEN 1 WHEN 'halted' THEN 2 WHEN 'running' THEN 3 WHEN 'queued' THEN 4 WHEN 'complete' THEN 5 ELSE 6 END,
                    priority DESC
            """, [m['id']])
            
            if not tasks:
                continue
            
            completed = sum(1 for t in tasks if t.get('status') == 'complete')
            total = len(tasks)
            pct = int((completed / total * 100)) if total > 0 else 0
            
            msg += f"📂 Phase {m['phase_number']}: {m['name']}\n"
            msg += f"   {progress_bar(completed, total)} {pct}%\n"
            
            for t in tasks:
                emoji = STATUS_EMOJI.get(t.get('status', ''), '❓')
                title = t.get('title', 'Untitled')
                if len(title) > 32:
                    title = title[:29] + "..."
                msg += f"   {emoji} {title}\n"
            msg += "\n"
        
        # Check for unassigned (exclude archived and Retry: duplicates)
        unassigned_tasks = query_all("""
            SELECT id, title, status, priority
            FROM tasks 
            WHERE milestone_id IS NULL
              AND status != 'archived'
              AND title NOT LIKE 'Retry:%%'
            ORDER BY 
                CASE status WHEN 'failed' THEN 1 WHEN 'running' THEN 2 ELSE 3 END,
                priority DESC
            LIMIT 10
        """)
        
        if unassigned_tasks:
            msg += "📦 Unassigned:\n"
            for t in unassigned_tasks:
                emoji = STATUS_EMOJI.get(t.get('status', ''), '❓')
                title = t.get('title', 'Untitled')
                if len(title) > 32:
                    title = title[:29] + "..."
                msg += f"   {emoji} {title}\n"
        
        # Telegram message limit is 4096 chars
        if len(msg) > 4000:
            msg = msg[:3950] + "\n\n... (truncated)"
        
        keyboard = [[InlineKeyboardButton("← Back to Roadmap", callback_data="back_roadmap")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Expand all error: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List recent tasks with status, priority, and milestone"""
    try:
        tasks = query_all("""
            SELECT t.id, t.title, t.status, t.priority,
                   m.name as milestone_name, m.phase_number
            FROM tasks t
            LEFT JOIN milestones m ON t.milestone_id = m.id
            ORDER BY t.created_at DESC 
            LIMIT 10
        """)
        
        if not tasks:
            await update.message.reply_text("📝 No tasks found")
            return
        
        msg = "📋 Recent Tasks:\n\n"
        for t in tasks:
            task_id = str(t['id'])[:8]
            emoji = STATUS_EMOJI.get(t.get('status', ''), '❓')
            title = t.get('title', 'Untitled')
            if len(title) > 30:
                title = title[:27] + "..."
            priority = t.get('priority', 0)
            phase = t.get('phase_number')
            
            msg += f"{emoji} #{task_id}\n"
            msg += f"   {title}\n"
            msg += f"   P{priority}"
            if phase:
                msg += f" | Phase {phase}"
            msg += "\n\n"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        logging.error(f"Tasks command error: {e}")
        await update.message.reply_text(f"❌ Tasks error: {str(e)}")


async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show queued tasks"""
    try:
        tasks = query_all("""
            SELECT t.title, t.priority, m.phase_number
            FROM tasks t
            LEFT JOIN milestones m ON t.milestone_id = m.id
            WHERE t.status IN ('queued', 'pending')
            ORDER BY t.priority DESC, t.created_at ASC
        """)
        
        if not tasks:
            await update.message.reply_text("📭 No queued tasks - all caught up!")
            return
        
        msg = "📋 Queued Tasks:\n\n"
        for t in tasks:
            title = t.get('title', 'Untitled')
            if len(title) > 40:
                title = title[:37] + "..."
            priority = t.get('priority', 0)
            phase = t.get('phase_number')
            
            msg += f"• P{priority}: {title}"
            if phase:
                msg += f" [Ph{phase}]"
            msg += "\n"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        logging.error(f"Queue command error: {e}")
        await update.message.reply_text(f"❌ Queue error: {str(e)}")


async def suggest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate smart task suggestions based on current state.
    
    Usage:
        /suggest - Show cached suggestions or generate rule-based ones
        /suggest refresh - Generate fresh AI-powered suggestions
        /suggest refresh <notes> - Generate AI suggestions with specific focus
    """
    try:
        # Parse arguments
        args = context.args if context.args else []
        use_ai = len(args) > 0 and args[0].lower() == 'refresh'
        focus_notes = ' '.join(args[1:]) if len(args) > 1 else None
        
        # Check for existing pending suggestions (unless refresh requested)
        if not use_ai:
            existing = query_all("SELECT COUNT(*) as cnt FROM suggestions WHERE status = 'pending'")
            if existing and existing[0].get('cnt', 0) > 0:
                await update.message.reply_text("📋 Showing cached suggestions...\nUse `/suggest refresh` for fresh AI suggestions.", parse_mode='Markdown')
                # Delete progress message
                try:
                    await progress_msg.delete()
                except:
                    pass
                
                await show_suggestion(update, context, page=0)
                return
        
        suggestions = []
        
        # If refresh requested, use AI suggestions
        if use_ai:
            progress_msg = await update.message.reply_text("🤖 Generating AI suggestions...\n⏳ Gathering system state..." + (f"\n📝 Focus: {focus_notes}" if focus_notes else ""))
            
            # Gather system state for AI
            # Update progress
            try:
                await progress_msg.edit_text("🤖 Generating AI suggestions...\n✅ Gathered system state\n⏳ Calling AI..." + (f"\n📝 Focus: {focus_notes}" if focus_notes else ""))
            except:
                pass
            
            system_state = {
                'milestones': query_all("""
                    SELECT m.id, m.name, m.phase_number, m.description,
                           COUNT(t.id) as total_tasks,
                           SUM(CASE WHEN t.status = 'complete' THEN 1 ELSE 0 END) as completed_tasks
                    FROM milestones m
                    LEFT JOIN tasks t ON t.milestone_id = m.id
                    GROUP BY m.id, m.name, m.phase_number, m.description
                    ORDER BY m.phase_number
                """),
                'recent_complete': query_all("""
                    SELECT title FROM tasks WHERE status = 'complete'
                    ORDER BY completed_at DESC LIMIT 5
                """),
                'failed_tasks': query_all("""
                    SELECT title, last_error FROM tasks WHERE status = 'failed'
                    ORDER BY updated_at DESC LIMIT 5
                """),
                'halted_tasks': query_all("""
                    SELECT title FROM tasks WHERE status = 'halted'
                    ORDER BY updated_at DESC LIMIT 5
                """),
                'pending_tasks': query_all("""
                    SELECT title FROM tasks WHERE status = 'pending'
                    ORDER BY priority DESC LIMIT 5
                """)
            }
            
            ai_suggestions = generate_ai_suggestions(system_state, focus_notes)
            
            # Update progress
            try:
                await progress_msg.edit_text("🤖 Generating AI suggestions...\n✅ Gathered system state\n✅ AI generated suggestions\n⏳ Saving..." + (f"\n📝 Focus: {focus_notes}" if focus_notes else ""))
            except:
                pass
            
            # Map AI suggestions to milestone IDs
            milestones = {m['phase_number']: m['id'] for m in (system_state.get('milestones') or []) if m and m.get('phase_number') is not None}
            
            for s in ai_suggestions:
                phase = s.get('phase', 0)
                suggestions.append({
                    'type': s.get('task_type', 'implementation'),
                    'title': s['title'],
                    'description': s['description'],
                    'milestone_id': milestones.get(phase),
                    'priority': s.get('priority', 5),
                    'ai_generated': True
                })
            
            if suggestions:
                # Clear old and save new
                execute_sql("DELETE FROM suggestions WHERE status = 'pending'")
                for s in suggestions:
                    execute_sql("""
                        INSERT INTO suggestions (title, description, task_type, milestone_id, priority, status)
                        VALUES (%s, %s, %s, %s, %s, 'pending')
                    """, [s['title'], s['description'], s.get('type', 'implementation'),
                          s.get('milestone_id'), s.get('priority', 5)])
                
                await show_suggestion(update, context, page=0)
                return
        
        # Fallback to rule-based suggestions
        # 1. Check for failed tasks that could be retried
        failed_tasks = query_all("""
            SELECT t.id, t.title, m.name as milestone_name, m.id as milestone_id
            FROM tasks t
            LEFT JOIN milestones m ON t.milestone_id = m.id
            WHERE t.status = 'failed'
            ORDER BY t.updated_at DESC
            LIMIT 3
        """)
        for task in failed_tasks:
            suggestions.append({
                'type': 'retry',
                'title': f"Retry: {task['title'][:40]}",
                'description': f"Previous attempt failed. Retry with improved approach.",
                'milestone_id': task.get('milestone_id'),
                'priority': 7,
                'original_task_id': str(task['id'])
            })
        
        # 2. Check incomplete phases and suggest next steps
        incomplete_phases = query_all("""
            SELECT m.id, m.name, m.phase_number, m.description,
                   COUNT(t.id) as total,
                   SUM(CASE WHEN t.status = 'complete' THEN 1 ELSE 0 END) as completed
            FROM milestones m
            LEFT JOIN tasks t ON t.milestone_id = m.id
            GROUP BY m.id, m.name, m.phase_number, m.description
            HAVING SUM(CASE WHEN t.status = 'complete' THEN 1 ELSE 0 END) < COUNT(t.id)
               OR COUNT(t.id) = 0
            ORDER BY m.phase_number
        """)
        
        # Phase-specific suggestions based on design doc
        phase_suggestions = {
            1: [  # Core Infrastructure
                ("Database optimization", "Add indexes and optimize slow queries"),
                ("Checkpoint compression", "Implement checkpoint data compression"),
                ("Audit log rotation", "Add log rotation and archival"),
            ],
            2: [  # Role-Based Agents
                ("Uncertainty detector", "Implement confidence scoring and halt triggers"),
                ("Drafter improvements", "Add code validation before draft submission"),
                ("Verifier enhancements", "Add security scanning to verification"),
            ],
            3: [  # Governance & Execution
                ("IMR Pentagon validation", "Implement full IMR checks for irreversible ops"),
                ("Rollback automation", "Add automated rollback for failed executions"),
                ("Compliance policies", "Define and implement compliance rule engine"),
            ],
            4: [  # Integration & Polish
                ("Grafana dashboard", "Create Agent-OS monitoring dashboard"),
                ("Daily digest", "Implement daily email/telegram summary"),
                ("CLI improvements", "Add interactive CLI for task management"),
                ("Error recovery wizard", "Guide users through fixing failed tasks"),
            ],
        }
        
        for phase in incomplete_phases[:2]:  # Limit to 2 phases
            phase_num = phase.get('phase_number', 0)
            if phase_num in phase_suggestions:
                for title, desc in phase_suggestions[phase_num][:2]:  # 2 suggestions per phase
                    # Check if similar task already exists
                    existing = query_one("""
                        SELECT id FROM tasks 
                        WHERE lower(title) LIKE %s AND milestone_id = %s
                    """, [f"%{title.lower()[:20]}%", phase['id']])
                    if not existing:
                        suggestions.append({
                            'type': 'new',
                            'title': title,
                            'description': desc,
                            'milestone_id': phase['id'],
                            'priority': 6 if phase_num <= 2 else 5,
                            'phase_name': phase['name']
                        })
        
        # 3. Suggest new phase if all current phases are >80% complete
        all_phases_progress = query_all("""
            SELECT m.phase_number,
                   COUNT(t.id) as total,
                   SUM(CASE WHEN t.status = 'complete' THEN 1 ELSE 0 END) as completed
            FROM milestones m
            LEFT JOIN tasks t ON t.milestone_id = m.id
            GROUP BY m.phase_number
        """)
        
        if all_phases_progress:
            all_high = all(
                (p.get('completed', 0) or 0) / max(p.get('total', 1), 1) >= 0.8 
                for p in all_phases_progress
            )
            if all_high:
                max_phase = max(p.get('phase_number', 0) for p in all_phases_progress)
                suggestions.append({
                    'type': 'phase',
                    'title': f"Create Phase {max_phase + 1}",
                    'description': "All current phases are >80% complete. Time for next phase?",
                    'priority': 8,
                    'new_phase_number': max_phase + 1
                })
        
        if not suggestions:
            await update.message.reply_text("✨ No suggestions right now - system looks good!\n\nTry /roadmap to review current state.")
            return
        
        # Clear old pending suggestions
        execute_sql("DELETE FROM suggestions WHERE status = 'pending'")
        
        # Save suggestions to database
        for s in suggestions:
            execute_sql("""
                INSERT INTO suggestions (title, description, task_type, milestone_id, priority, status, original_task_id)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s)
            """, [s['title'], s['description'], s.get('type', 'implementation'), 
                  s.get('milestone_id'), s.get('priority', 5), s.get('original_task_id')])
        
        # Display first suggestion with buttons
        await show_suggestion(update, context, page=0)
        
    except Exception as e:
        logging.error(f"Suggest command error: {e}\n{traceback.format_exc()}")
        try:
            await update.message.reply_text(f"❌ Suggest error: {str(e)}")
        except:
            pass


async def show_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0, edit: bool = False):
    """Display a single suggestion with approve/decline/skip buttons"""
    try:
        suggestions = query_all("""
            SELECT s.*, m.name as milestone_name, m.phase_number
            FROM suggestions s
            LEFT JOIN milestones m ON s.milestone_id = m.id
            WHERE s.status = 'pending'
            ORDER BY s.priority DESC, s.id
        """)
        
        if not suggestions:
            msg = "✅ All suggestions reviewed!\n\nApproved tasks are now in the queue.\nUse /queue to see them or /run to start."
            keyboard = [[InlineKeyboardButton("🚀 View Queue", callback_data="back_queue")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            if edit:
                try:
                    await update.callback_query.edit_message_text(msg, reply_markup=reply_markup)
                except Exception:
                    pass
            else:
                await update.message.reply_text(msg, reply_markup=reply_markup)
            return
        
        # Wrap page number
        page = page % len(suggestions)
        
        s = suggestions[page]
        total = len(suggestions)
        
        type_emoji = {'retry': '🔄', 'new': '✨', 'phase': '📦'}.get(s.get('task_type'), '📋')
        
        msg = f"💡 Suggestion {page + 1}/{total}\n\n"
        msg += f"{type_emoji} {s['title']}\n\n"
        msg += f"📝 {s['description']}\n\n"
        
        if s.get('milestone_name'):
            msg += f"🗺️ Phase {s.get('phase_number', '?')}: {s['milestone_name']}\n"
        msg += f"📊 Priority: P{s.get('priority', 5)}\n"
        msg += f"🆔 #{s['id']}"
        
        # Calculate next page (skip to next, wrap around)
        next_page = (page + 1) % total
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"sug_approve_{s['id']}_{page}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"sug_decline_{s['id']}_{page}"),
            ],
            [
                InlineKeyboardButton(f"⏭️ Skip ({next_page + 1}/{total})", callback_data=f"sug_skip_{next_page}"),
                InlineKeyboardButton("✅ Approve All", callback_data="sug_approve_all"),
            ],
            [
                InlineKeyboardButton("🚫 Done Reviewing", callback_data="sug_done"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit:
            try:
                await update.callback_query.edit_message_text(msg, reply_markup=reply_markup)
            except Exception as e:
                # If message is same, just answer the callback
                if "not modified" in str(e).lower():
                    await update.callback_query.answer("No more suggestions in that direction")
                else:
                    raise e
        else:
            await update.message.reply_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Show suggestion error: {e}")
        msg = f"❌ Error: {str(e)}"
        if edit:
            try:
                await update.callback_query.edit_message_text(msg)
            except:
                pass
        else:
            await update.message.reply_text(msg)


async def suggestion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle suggestion approve/decline/skip buttons"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data
        
        if data.startswith("sug_approve_all"):
            # Approve all pending suggestions
            pending = query_all("SELECT * FROM suggestions WHERE status = 'pending'")
            for s in pending:
                await create_task_from_suggestion(s)
            execute_sql("UPDATE suggestions SET status = 'approved', approved_at = NOW() WHERE status = 'pending'")
            msg = f"✅ Approved {len(pending)} suggestions!\n\nUse /queue to see new tasks or /run to start."
            keyboard = [[InlineKeyboardButton("🚀 View Queue", callback_data="back_queue")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        elif data.startswith("sug_approve_"):
            # Format: sug_approve_{id}_{page}
            parts = data.replace("sug_approve_", "").split("_")
            sug_id = int(parts[0])
            suggestion = query_one("SELECT * FROM suggestions WHERE id = %s", [sug_id])
            if suggestion:
                task_id = await create_task_from_suggestion(suggestion)
                execute_sql("UPDATE suggestions SET status = 'approved', approved_at = NOW(), task_id = %s WHERE id = %s", 
                           [task_id, sug_id])
            await show_suggestion(update, context, page=0, edit=True)
            
        elif data.startswith("sug_decline_"):
            # Format: sug_decline_{id}_{page}
            parts = data.replace("sug_decline_", "").split("_")
            sug_id = int(parts[0])
            execute_sql("UPDATE suggestions SET status = 'declined', declined_at = NOW() WHERE id = %s", [sug_id])
            await show_suggestion(update, context, page=0, edit=True)
            
        elif data.startswith("sug_skip_"):
            page = int(data.replace("sug_skip_", ""))
            await show_suggestion(update, context, page=page, edit=True)
            
        elif data == "sug_done":
            # Mark remaining as skipped, show summary
            remaining = query_one("SELECT COUNT(*) as count FROM suggestions WHERE status = 'pending'")
            approved = query_one("SELECT COUNT(*) as count FROM suggestions WHERE status = 'approved'")
            declined = query_one("SELECT COUNT(*) as count FROM suggestions WHERE status = 'declined'")
            
            execute_sql("DELETE FROM suggestions WHERE status = 'pending'")
            
            msg = "📋 Suggestion Review Complete\n\n"
            msg += f"✅ Approved: {approved.get('count', 0) if approved else 0}\n"
            msg += f"❌ Declined: {declined.get('count', 0) if declined else 0}\n"
            msg += f"⏭️ Skipped: {remaining.get('count', 0) if remaining else 0}\n\n"
            msg += "Use /queue to see new tasks or /run to start."
            
            keyboard = [[InlineKeyboardButton("🚀 View Queue", callback_data="back_queue")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            
    except Exception as e:
        logging.error(f"Suggestion callback error: {e}")
        try:
            await query.edit_message_text(f"❌ Error: {str(e)}")
        except:
            pass


async def create_task_from_suggestion(suggestion: dict) -> str:
    """Create a task from an approved suggestion"""
    task_id = str(uuid.uuid4())
    
    # Get project ID - for retries, use original task's project; otherwise use agent-os-v3
    project_id = None
    original_task_id = suggestion.get('original_task_id')
    
    if original_task_id:
        # This is a retry - get project from original task
        original = query_one("SELECT project_id, description FROM tasks WHERE id = %s", [original_task_id])
        if original:
            project_id = original.get('project_id')
            # Also inherit description if not provided
            if not suggestion.get('description') or 'Previous attempt failed' in suggestion.get('description', ''):
                suggestion['description'] = original.get('description', suggestion.get('description', ''))
    
    if not project_id:
        # Default to agent-os-v3 project (not just any first project!)
        project = query_one("SELECT id FROM projects WHERE name = 'agent-os-v3' LIMIT 1")
        if not project:
            # Fallback to first project if agent-os-v3 doesn't exist
            project = query_one("SELECT id FROM projects ORDER BY created_at DESC LIMIT 1")
        project_id = project['id'] if project else None
    
    execute_sql("""
        INSERT INTO tasks (id, title, description, task_type, priority, status, milestone_id, project_id, current_phase)
        VALUES (%s, %s, %s, %s, %s, 'queued', %s, %s, 'preparation')
    """, [task_id, suggestion['title'], suggestion.get('description', ''), 
          'implementation', suggestion.get('priority', 5),
          suggestion.get('milestone_id'), project_id])
    
    return task_id


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyze a failed/halted task and suggest remediation"""
    try:
        args = context.args
        
        if not args:
            # Auto-cleanup duplicates first
            cleanup_result = cleanup_duplicate_tasks()
            
            # Get unique failed/halted tasks (deduplicated)
            failed_tasks = get_unique_failed_tasks()
            
            if not failed_tasks:
                await update.message.reply_text("✅ No failed or halted tasks to analyze!")
                return
            
            msg = "🔍 *Failed/Halted Tasks*\n"
            
            if cleanup_result['archived'] > 0:
                msg += f"🧹 _Auto-cleaned {cleanup_result['archived']} duplicates_\n"
            
            msg += "\n"
            
            # Show tasks with descriptions
            for i, t in enumerate(failed_tasks[:5], 1):
                base_title = get_base_task_title(t.get('title', 'Untitled'))
                status_emoji = STATUS_EMOJI.get(t.get('status', ''), '❓')
                retry_info = f" ×{t.get('retry_count', 0)+1}" if t.get('retry_count', 0) > 0 else ""
                
                msg += f"{status_emoji} *{base_title}*{retry_info}\n"
                
                # Show description snippet
                desc = t.get('description', '')
                if desc:
                    if len(desc) > 80:
                        desc = desc[:77] + "..."
                    msg += f"   _{desc}_\n"
                msg += "\n"
            
            if len(failed_tasks) > 5:
                msg += f"_...and {len(failed_tasks) - 5} more_\n\n"
            
            msg += "Select to analyze:"
            
            keyboard = []
            for t in failed_tasks[:8]:
                base_title = get_base_task_title(t.get('title', 'Untitled'))
                if len(base_title) > 25:
                    base_title = base_title[:22] + "..."
                status_emoji = STATUS_EMOJI.get(t.get('status', ''), '❓')
                keyboard.append([InlineKeyboardButton(f"{status_emoji} {base_title}", callback_data=f"analyze_{t['id']}")])
            
            keyboard.append([
                InlineKeyboardButton("🗑️ Archive All", callback_data="analyze_archive_all"),
                InlineKeyboardButton("📋 Queue", callback_data="back_queue"),
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
            return
        
        # Analyze specific task
        task_id_prefix = args[0].replace('#', '')
        await show_task_analysis(update, context, task_id_prefix)
        
    except Exception as e:
        logging.error(f"Analyze command error: {e}")
        await update.message.reply_text(f"❌ Analysis error: {str(e)}")


async def show_task_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: str, edit: bool = False):
    """Show detailed analysis of a task's failures"""
    try:
        # Find the task
        task = query_one("""
            SELECT t.*, p.name as project_name, m.name as milestone_name, m.phase_number
            FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN milestones m ON t.milestone_id = m.id
            WHERE CAST(t.id AS TEXT) LIKE %s
            LIMIT 1
        """, [f"{task_id}%"])
        
        if not task:
            msg = f"❌ Task #{task_id} not found"
            if edit:
                await update.callback_query.edit_message_text(msg)
            else:
                await update.message.reply_text(msg)
            return
        
        full_task_id = str(task['id'])
        
        # Get failure history from checkpoints
        failures = get_task_failure_history(full_task_id)
        
        # Get related tasks (previous attempts)
        related = get_related_tasks(task.get('title', ''))
        
        # Analyze the failure
        latest_error = None
        if failures:
            error_details = failures[0].get('error_details')
            if error_details:
                if isinstance(error_details, dict):
                    latest_error = error_details.get('error', str(error_details))
                else:
                    latest_error = str(error_details)
        
        if not latest_error and task.get('error_message'):
            latest_error = task.get('error_message')
        
        failure_info = categorize_failure(latest_error or '')
        
        # Build analysis message
        status_emoji = STATUS_EMOJI.get(task.get('status', ''), '❓')
        base_title = get_base_task_title(task.get('title', 'Untitled'))
        msg = f"🔍 *Task Analysis*\n\n"
        msg += f"{status_emoji} *{base_title}*\n"
        msg += f"🆔 `{full_task_id[:8]}...{full_task_id[-4:]}`\n\n"
        
        # Task description
        desc = task.get('description', '')
        if desc:
            if len(desc) > 200:
                desc = desc[:197] + "..."
            msg += f"📝 _{desc}_\n\n"
        
        # Failure category
        category_emoji = {
            'environment': '🔧',
            'code_bug': '🐛', 
            'task_ambiguity': '❓',
            'external': '🌐',
            'git': '📦',
            'performance': '⏱️',
            'unknown': '❔'
        }.get(failure_info['category'], '❔')
        
        msg += f"*Diagnosis:*\n"
        msg += f"{category_emoji} Category: {failure_info['category'].replace('_', ' ').title()}\n"
        msg += f"📋 {failure_info['description']}\n\n"
        
        # Latest error
        if latest_error:
            error_short = latest_error[:150] + "..." if len(latest_error) > 150 else latest_error
            msg += f"*Latest Error:*\n`{error_short}`\n\n"
        
        # Failure history summary
        msg += f"*History:*\n"
        msg += f"• {len(failures)} checkpoint failure(s)\n"
        msg += f"• {len([r for r in related if r.get('status') in ('failed', 'halted')])} related failed attempt(s)\n"
        msg += f"• Failed at phase: {task.get('current_phase', 'unknown')}\n\n"
        
        # Remediation suggestion
        remediation_text = {
            'cleanup_branch': "🧹 Clean up existing git branch and retry",
            'report_bug': "🐛 This is a code bug - needs developer fix",
            'refine_task': "✏️ Task needs more specific requirements",
            'wait_retry': "⏳ Wait a few minutes and retry",
            'manual_resolve': "👤 Needs manual intervention",
            'decompose_task': "✂️ Break this into smaller tasks",
            'manual_review': "🔍 Review error details manually"
        }
        
        msg += f"*Suggested Action:*\n{remediation_text.get(failure_info['remediation'], '🔍 Review manually')}\n"
        
        # Build action buttons based on failure type
        keyboard = []
        
        if failure_info['remediation'] == 'cleanup_branch':
            keyboard.append([
                InlineKeyboardButton("🧹 Clean & Retry", callback_data=f"fix_cleanup_{full_task_id}"),
            ])
        elif failure_info['remediation'] == 'refine_task':
            keyboard.append([
                InlineKeyboardButton("✏️ Refine Task", callback_data=f"fix_refine_{full_task_id}"),
            ])
        elif failure_info['remediation'] == 'decompose_task':
            keyboard.append([
                InlineKeyboardButton("✂️ Split Task", callback_data=f"fix_split_{full_task_id}"),
            ])
        
        # Always show these options
        keyboard.append([
            InlineKeyboardButton("🔄 Simple Retry", callback_data=f"task_retry_{full_task_id}"),
            InlineKeyboardButton("🗑️ Archive", callback_data=f"task_archive_{full_task_id}"),
        ])
        keyboard.append([
            InlineKeyboardButton("📜 View Logs", callback_data=f"fix_logs_{full_task_id}"),
            InlineKeyboardButton("← Back", callback_data="back_failed"),
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit:
            await update.callback_query.edit_message_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Task analysis error: {e}")
        msg = f"❌ Analysis error: {str(e)}"
        if edit:
            try:
                await update.callback_query.edit_message_text(msg)
            except:
                pass
        else:
            await update.message.reply_text(msg)


async def fix_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle fix/remediation actions for failed tasks"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data
        
        if data.startswith("analyze_"):
            task_id = data.replace("analyze_", "")
            await show_task_analysis(update, context, task_id, edit=True)
            
        elif data.startswith("fix_cleanup_"):
            task_id = data.replace("fix_cleanup_", "")
            
            # Get task to find branch name
            task = query_one("SELECT id, title FROM tasks WHERE id = %s", [task_id])
            if not task:
                await query.edit_message_text("❌ Task not found")
                return
            
            # Clean up the branch by deleting it
            short_id = str(task['id']).replace('-', '')[:8]
            branch_name = f"aos/implementation/{short_id}"
            
            msg = f"🧹 *Cleanup in Progress*\n\n"
            msg += f"Attempting to delete branch: `{branch_name}`\n\n"
            msg += f"After cleanup, the task will be re-queued.\n\n"
            msg += "⏳ Please wait..."
            
            await query.edit_message_text(msg, parse_mode="Markdown")
            
            # Queue the task for retry with cleanup flag
            execute_sql("""
                UPDATE tasks 
                SET status = 'queued', 
                    current_phase = 'preparation',
                    error_message = NULL,
                    updated_at = NOW()
                WHERE id = %s
            """, [task_id])
            
            # Also mark related failed branches for cleanup in checkpoints
            execute_sql("""
                INSERT INTO checkpoints (task_id, phase, step_name, status, state_snapshot)
                VALUES (%s, 'preparation', 'branch_cleanup', 'pending', %s)
            """, [task_id, f'{{"branch": "{branch_name}", "action": "delete"}}'])
            
            msg = f"✅ *Cleanup Scheduled*\n\n"
            msg += f"Branch `{branch_name}` marked for deletion.\n"
            msg += f"Task re-queued for retry.\n\n"
            msg += "Use /run to start the task."
            
            keyboard = [[InlineKeyboardButton("🚀 Go to Queue", callback_data="back_queue")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
        elif data.startswith("fix_refine_"):
            task_id = data.replace("fix_refine_", "")
            task = query_one("SELECT id, title, description FROM tasks WHERE id = %s", [task_id])
            
            if not task:
                await query.edit_message_text("❌ Task not found")
                return
            
            msg = f"✏️ *Refine Task*\n\n"
            msg += f"*Current Title:*\n{task.get('title', 'Untitled')}\n\n"
            msg += f"*Current Description:*\n{task.get('description', 'No description')[:300]}\n\n"
            msg += f"To refine this task, send a message with:\n"
            msg += f"`/refine {str(task_id)[:8]} <new description>`\n\n"
            msg += "Tips for better task descriptions:\n"
            msg += "• Be specific about what files to create/modify\n"
            msg += "• Include example inputs/outputs\n"
            msg += "• Reference existing patterns in the codebase\n"
            msg += "• Limit scope to one specific change"
            
            keyboard = [[InlineKeyboardButton("← Back to Analysis", callback_data=f"analyze_{task_id}")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
        elif data.startswith("fix_split_"):
            task_id = data.replace("fix_split_", "")
            task = query_one("SELECT id, title, description, milestone_id, priority FROM tasks WHERE id = %s", [task_id])
            
            if not task:
                await query.edit_message_text("❌ Task not found")
                return
            
            # Suggest task decomposition
            msg = f"✂️ *Split Task*\n\n"
            msg += f"*Original:* {task.get('title', 'Untitled')}\n\n"
            msg += "Complex tasks often fail. Consider splitting into:\n\n"
            msg += "1️⃣ *Preparation* - Create necessary files/folders\n"
            msg += "2️⃣ *Core Logic* - Implement main functionality\n"
            msg += "3️⃣ *Integration* - Connect to existing code\n"
            msg += "4️⃣ *Testing* - Add tests and validation\n\n"
            msg += "Use /suggest to generate specific sub-tasks, or:\n"
            msg += f"`/addtask <title>` to add manually"
            
            keyboard = [
                [InlineKeyboardButton("✨ Auto-Split", callback_data=f"fix_autosplit_{task_id}")],
                [InlineKeyboardButton("← Back to Analysis", callback_data=f"analyze_{task_id}")]
            ]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
        elif data.startswith("fix_autosplit_"):
            task_id = data.replace("fix_autosplit_", "")
            task = query_one("SELECT * FROM tasks WHERE id = %s", [task_id])
            
            if not task:
                await query.edit_message_text("❌ Task not found")
                return
            
            # Create sub-tasks
            base_title = task.get('title', 'Task').replace('Retry: ', '')
            milestone_id = task.get('milestone_id')
            project_id = task.get('project_id')
            priority = task.get('priority', 5)
            
            sub_tasks = [
                (f"[Part 1] Setup for: {base_title}", "Create necessary file structure and imports", priority + 1),
                (f"[Part 2] Core: {base_title}", "Implement the main functionality", priority),
                (f"[Part 3] Integrate: {base_title}", "Connect to existing system", priority - 1),
            ]
            
            created_ids = []
            for title, desc, prio in sub_tasks:
                new_id = str(uuid.uuid4())
                execute_sql("""
                    INSERT INTO tasks (id, project_id, milestone_id, title, description, task_type, status, priority, current_phase)
                    VALUES (%s, %s, %s, %s, %s, 'implementation', 'queued', %s, 'preparation')
                """, [new_id, project_id, milestone_id, title[:100], desc, max(1, min(10, prio))])
                created_ids.append(new_id[:8])
            
            # Archive the original
            execute_sql("UPDATE tasks SET status = 'archived', updated_at = NOW() WHERE id = %s", [task_id])
            
            msg = f"✂️ *Task Split Complete*\n\n"
            msg += f"Original task archived.\n"
            msg += f"Created {len(sub_tasks)} sub-tasks:\n\n"
            for i, (title, _, _) in enumerate(sub_tasks, 1):
                msg += f"{i}. {title[:50]}...\n"
            msg += f"\nUse /run to start working on them."
            
            keyboard = [[InlineKeyboardButton("🚀 View Queue", callback_data="back_queue")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
        elif data.startswith("fix_logs_"):
            task_id = data.replace("fix_logs_", "")
            
            # Get recent checkpoints for this task
            checkpoints = query_all("""
                SELECT id, phase, step_name, status, error_details, created_at
                FROM checkpoints
                WHERE task_id = %s
                ORDER BY created_at DESC
                LIMIT 5
            """, [task_id])
            
            msg = f"📜 *Recent Checkpoints*\n\n"
            
            if not checkpoints:
                msg += "No checkpoint logs found."
            else:
                for cp in checkpoints:
                    status_emoji = {'complete': '✅', 'failed': '❌', 'pending': '⏳'}.get(cp.get('status', ''), '❓')
                    msg += f"{status_emoji} *{cp.get('phase', '?')}/{cp.get('step_name', '?')}*\n"
                    
                    if cp.get('error_details'):
                        err = cp['error_details']
                        if isinstance(err, dict):
                            err_text = err.get('error', str(err))[:100]
                        else:
                            err_text = str(err)[:100]
                        msg += f"└ `{err_text}`\n"
                    msg += "\n"
            
            keyboard = [[InlineKeyboardButton("← Back to Analysis", callback_data=f"analyze_{task_id}")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
        elif data == "analyze_archive_all":
            # Archive all failed/halted tasks
            result = execute_sql("""
                UPDATE tasks 
                SET status = 'archived', updated_at = NOW()
                WHERE status IN ('failed', 'halted')
                RETURNING id
            """)
            
            # Count archived
            count = query_one("SELECT COUNT(*) as c FROM tasks WHERE status = 'archived' AND updated_at > NOW() - INTERVAL '1 minute'")
            archived_count = count.get('c', 0) if count else 0
            
            msg = f"🗑️ *Archived {archived_count} failed tasks*\n\n"
            msg += "All failed and halted tasks have been archived.\n"
            msg += "Use /suggest to generate new task ideas."
            
            keyboard = [[InlineKeyboardButton("✨ Suggest Tasks", callback_data="back_queue")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
        elif data == "back_failed":
            # Show deduplicated list of failed tasks
            cleanup_result = cleanup_duplicate_tasks()
            failed_tasks = get_unique_failed_tasks()
            
            if not failed_tasks:
                await query.edit_message_text("✅ No failed tasks!")
                return
            
            msg = "🔍 *Failed/Halted Tasks*\n"
            if cleanup_result['archived'] > 0:
                msg += f"🧹 _Auto-cleaned {cleanup_result['archived']} duplicates_\n"
            msg += "\n"
            
            # Show tasks with descriptions
            for t in failed_tasks[:5]:
                base_title = get_base_task_title(t.get('title', 'Untitled'))
                status_emoji = STATUS_EMOJI.get(t.get('status', ''), '❓')
                retry_info = f" ×{t.get('retry_count', 0)+1}" if t.get('retry_count', 0) > 0 else ""
                
                msg += f"{status_emoji} *{base_title}*{retry_info}\n"
                desc = t.get('description', '')
                if desc:
                    if len(desc) > 80:
                        desc = desc[:77] + "..."
                    msg += f"   _{desc}_\n"
                msg += "\n"
            
            if len(failed_tasks) > 5:
                msg += f"_...and {len(failed_tasks) - 5} more_\n\n"
            
            msg += "Select to analyze:"
            
            keyboard = []
            for t in failed_tasks[:8]:
                base_title = get_base_task_title(t.get('title', 'Untitled'))
                if len(base_title) > 25:
                    base_title = base_title[:22] + "..."
                status_emoji = STATUS_EMOJI.get(t.get('status', ''), '❓')
                keyboard.append([InlineKeyboardButton(f"{status_emoji} {base_title}", callback_data=f"analyze_{t['id']}")])
            
            keyboard.append([
                InlineKeyboardButton("🗑️ Archive All", callback_data="analyze_archive_all"),
                InlineKeyboardButton("📋 Queue", callback_data="back_queue"),
            ])
            
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            
    except Exception as e:
        logging.error(f"Fix callback error: {e}")
        try:
            await query.edit_message_text(f"❌ Error: {str(e)}")
        except:
            pass


async def refine_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refine a task's description for better results"""
    try:
        args = context.args
        
        if len(args) < 2:
            await update.message.reply_text(
                "📝 *Refine Task*\n\n"
                "Usage: `/refine <task_id> <new description>`\n\n"
                "Example:\n"
                "`/refine abc123 Create a Python script that reads /opt/agent-os/config.yaml and sends daily stats via Telegram`",
                parse_mode="Markdown"
            )
            return
        
        task_id_prefix = args[0].replace('#', '')
        new_description = ' '.join(args[1:])
        
        # Find the task
        task = query_one("""
            SELECT id, title, description FROM tasks 
            WHERE CAST(id AS TEXT) LIKE %s
            LIMIT 1
        """, [f"{task_id_prefix}%"])
        
        if not task:
            await update.message.reply_text(f"❌ Task #{task_id_prefix} not found")
            return
        
        # Update the task
        execute_sql("""
            UPDATE tasks 
            SET description = %s, 
                status = 'queued',
                current_phase = 'preparation',
                error_message = NULL,
                updated_at = NOW()
            WHERE id = %s
        """, [new_description, task['id']])
        
        msg = f"✅ *Task Refined*\n\n"
        msg += f"*Title:* {task.get('title', 'Untitled')}\n\n"
        msg += f"*New Description:*\n{new_description[:500]}\n\n"
        msg += "Task re-queued. Use /run to start it."
        
        keyboard = [[InlineKeyboardButton("🚀 Go to Queue", callback_data="back_queue")]]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Refine command error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def addphase_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new phase/milestone"""
    try:
        args = context.args
        if not args:
            # Show current phases and prompt
            phases = query_all("SELECT phase_number, name FROM milestones ORDER BY phase_number")
            msg = "📦 Add New Phase\n\n"
            msg += "Current phases:\n"
            for p in phases:
                msg += f"  {p['phase_number']}. {p['name']}\n"
            
            next_num = max(p['phase_number'] for p in phases) + 1 if phases else 1
            msg += f"\nUsage: /addphase {next_num} Phase Name Here\n"
            msg += f"Example: /addphase {next_num} Advanced Monitoring"
            
            await update.message.reply_text(msg)
            return
        
        # Parse: /addphase 5 Phase Name Here
        try:
            phase_num = int(args[0])
            phase_name = ' '.join(args[1:])
        except ValueError:
            # Maybe they just gave a name, auto-assign number
            phases = query_all("SELECT MAX(phase_number) as max_num FROM milestones")
            phase_num = (phases[0].get('max_num', 0) or 0) + 1
            phase_name = ' '.join(args)
        
        if not phase_name:
            await update.message.reply_text("❌ Please provide a phase name.\nUsage: /addphase 5 Phase Name")
            return
        
        # Get project ID
        project = query_one("SELECT id FROM projects LIMIT 1")
        project_id = project['id'] if project else None
        
        execute_sql("""
            INSERT INTO milestones (name, phase_number, status, project_id)
            VALUES (%s, %s, 'planned', %s)
        """, [phase_name, phase_num, project_id])
        
        await update.message.reply_text(f"✅ Created Phase {phase_num}: {phase_name}\n\nUse /suggest to get task ideas for this phase.")
        
    except Exception as e:
        logging.error(f"Add phase error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show queued tasks with ability to run specific one"""
    try:
        args = context.args
        
        # If task ID provided, show that specific task with visual progress
        if args:
            task_id_prefix = args[0].replace('#', '')
            task = query_one("""
                SELECT t.*, p.name as project_name, m.name as milestone_name, m.phase_number
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                LEFT JOIN milestones m ON t.milestone_id = m.id
                WHERE CAST(t.id AS TEXT) LIKE %s
                LIMIT 1
            """, [f"{task_id_prefix}%"])
            
            if not task:
                await update.message.reply_text(f"❌ Task #{task_id_prefix} not found")
                return
            
            # Use visual progress renderer
            msg = render_task_progress(task)
            
            task_id = str(task['id'])
            status = task.get('status', '')
            
            keyboard = []
            if status in ('queued', 'pending'):
                keyboard.append([
                    InlineKeyboardButton("▶️ Start Task", callback_data=f"task_start_{task_id}"),
                    InlineKeyboardButton("⏸️ Hold", callback_data=f"task_hold_{task_id}"),
                ])
            elif status in ('failed', 'halted'):
                keyboard.append([
                    InlineKeyboardButton("🔍 Analyze", callback_data=f"analyze_{task_id}"),
                    InlineKeyboardButton("🔄 Retry", callback_data=f"task_retry_{task_id}"),
                ])
                keyboard.append([
                    InlineKeyboardButton("🗑️ Archive", callback_data=f"task_archive_{task_id}"),
                ])
            elif status in ('running', 'in_progress'):
                keyboard.append([
                    InlineKeyboardButton("⏸️ Pause", callback_data=f"task_hold_{task_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"task_fail_{task_id}"),
                ])
            
            keyboard.append([InlineKeyboardButton("📋 View Queue", callback_data="back_queue")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(msg, reply_markup=reply_markup)
            return
        
        # No args - show queue with clickable tasks
        tasks = query_all("""
            SELECT t.id, t.title, t.priority, t.status, t.current_phase, m.phase_number
            FROM tasks t
            LEFT JOIN milestones m ON t.milestone_id = m.id
            WHERE t.status IN ('queued', 'pending')
            ORDER BY t.priority DESC, t.created_at ASC
            LIMIT 10
        """)
        
        if not tasks:
            # Check for running or failed tasks
            active = query_one("SELECT COUNT(*) as c FROM tasks WHERE status IN ('running', 'in_progress')")
            failed = query_one("SELECT COUNT(*) as c FROM tasks WHERE status = 'failed'")
            
            msg = "📭 No queued tasks!\n"
            if active and active.get('c', 0) > 0:
                msg += f"\n🔄 {active['c']} task(s) currently running"
            if failed and failed.get('c', 0) > 0:
                msg += f"\n❌ {failed['c']} failed task(s) - /tasks to review"
            msg += "\n\nUse /suggest to generate new task ideas."
            await update.message.reply_text(msg)
            return
        
        msg = "🚀 Ready to Run\n\nSelect a task to view details:\n"
        keyboard = []
        
        for t in tasks:
            task_id = str(t['id'])[:8]
            title = t.get('title', 'Untitled')
            if len(title) > 25:
                title = title[:22] + "..."
            priority = t.get('priority', 0)
            phase = t.get('phase_number', '-')
            
            btn_text = f"P{priority} | Ph{phase} | {title}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"task_view_{t['id']}")])
        
        # Add run next button
        keyboard.append([InlineKeyboardButton("▶️ Run Next (Highest Priority)", callback_data="task_run_next")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(msg, reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Run command error: {e}")
        await update.message.reply_text(f"❌ Run error: {str(e)}")


async def task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle task-related button callbacks"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data
        
        if data.startswith("task_view_"):
            task_id = data.replace("task_view_", "")
            task = query_one("""
                SELECT t.*, p.name as project_name, m.name as milestone_name, m.phase_number
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                LEFT JOIN milestones m ON t.milestone_id = m.id
                WHERE t.id = %s
            """, [task_id])
            
            if not task:
                await query.edit_message_text("❌ Task not found")
                return
            
            # Use the visual progress renderer
            msg = render_task_progress(task)
            
            keyboard = []
            status = task.get('status', '')
            if status in ('queued', 'pending'):
                keyboard.append([
                    InlineKeyboardButton("▶️ Start", callback_data=f"task_start_{task_id}"),
                    InlineKeyboardButton("⏸️ Hold", callback_data=f"task_hold_{task_id}"),
                ])
            elif status in ('failed', 'halted'):
                keyboard.append([
                    InlineKeyboardButton("🔍 Analyze", callback_data=f"analyze_{task_id}"),
                    InlineKeyboardButton("🔄 Retry", callback_data=f"task_retry_{task_id}"),
                ])
                keyboard.append([
                    InlineKeyboardButton("🗑️ Archive", callback_data=f"task_archive_{task_id}"),
                ])
            elif status in ('running', 'in_progress'):
                keyboard.append([
                    InlineKeyboardButton("⏸️ Pause", callback_data=f"task_hold_{task_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"task_fail_{task_id}"),
                ])
            
            keyboard.append([InlineKeyboardButton("← Back", callback_data="back_queue")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
            
        elif data.startswith("task_start_"):
            task_id = data.replace("task_start_", "")
            # Set to pending so orchestrator picks it up, give it high priority
            execute_sql("UPDATE tasks SET status = 'pending', priority = priority + 10, updated_at = NOW() WHERE id = %s", [task_id])
            task = query_one("SELECT * FROM tasks WHERE id = %s", [task_id])
            if task:
                task['status'] = 'pending'
                msg = render_task_progress(task)
                msg += "\n\n▶️ Task queued with boosted priority!"
                msg += "\n⏳ Orchestrator runs every 10 min (or trigger manually)"
                keyboard = [
                    [InlineKeyboardButton("🚀 Run Now", callback_data=f"task_run_now_{task_id}")],
                    [InlineKeyboardButton("← Back to Queue", callback_data="back_queue")]
                ]
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.edit_message_text("▶️ Task queued!\n\nOrchestrator will pick it up soon.")
            
        elif data.startswith("task_hold_"):
            task_id = data.replace("task_hold_", "")
            execute_sql("UPDATE tasks SET status = 'pending', updated_at = NOW() WHERE id = %s", [task_id])
            await query.edit_message_text("⏸️ Task paused.\n\nUse /run to see queue.")
            
        elif data.startswith("task_retry_"):
            task_id = data.replace("task_retry_", "")
            execute_sql("UPDATE tasks SET status = 'queued', updated_at = NOW(), current_phase = 'preparation' WHERE id = %s", [task_id])
            await query.edit_message_text("🔄 Task queued for retry.\n\nUse /run to start it.")
            
        elif data.startswith("task_archive_"):
            task_id = data.replace("task_archive_", "")
            execute_sql("UPDATE tasks SET status = 'archived', updated_at = NOW() WHERE id = %s", [task_id])
            await query.edit_message_text("🗑️ Task archived.\n\nUse /run to see remaining queue.")
            
        elif data.startswith("task_fail_"):
            task_id = data.replace("task_fail_", "")
            execute_sql("UPDATE tasks SET status = 'failed', updated_at = NOW() WHERE id = %s", [task_id])
            await query.edit_message_text("❌ Task cancelled.\n\nUse /run to see queue.")
            
        elif data.startswith("task_run_now_"):
            task_id = data.replace("task_run_now_", "")
            
            # Get task info before running
            task = query_one("SELECT * FROM tasks WHERE id = %s", [task_id])
            task_title = task.get('title', 'Unknown')[:40] if task else 'Unknown'
            
            # Edit original message to show initiated
            await query.edit_message_text(f"✅ Task run initiated!\n\n📋 {task_title}\n🆔 {task_id[:8]}...\n\n⏳ Executing now...")
            
            # Send NEW message with running status
            chat_id = query.message.chat_id
            progress_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"🚀 Running Task...\n\n📋 {task_title}\n\n⏳ Phase: Preparation\n▓░░░░░░░░░░░░░░░░░░░ 5%"
            )
            
            # Run orchestrator
            import subprocess
            try:
                result = subprocess.run(
                    ["/opt/agent-os-v3/run-v3.sh"],
                    capture_output=True,
                    text=True,
                    timeout=180,
                    cwd="/opt/agent-os-v3"
                )
                
                # Check task status after run
                task = query_one("SELECT * FROM tasks WHERE id = %s", [task_id])
                if task:
                    msg = render_task_progress(task)
                    status = task.get('status', 'unknown')
                    if status == 'complete':
                        msg += "\n\n✅ Task completed successfully!"
                    elif status == 'failed':
                        error = task.get('last_error', 'Unknown error')
                        msg += f"\n\n❌ Task failed: {error[:150]}"
                    elif status == 'halted':
                        msg += "\n\n⚠️ Task halted - review required"
                    elif status == 'needs_revision':
                        msg += "\n\n📝 Revision required - check issues"
                    else:
                        msg += f"\n\n🔄 Status: {status}"
                    
                    keyboard = [
                        [InlineKeyboardButton("🔄 Retry", callback_data=f"task_retry_{task_id}")],
                        [InlineKeyboardButton("← Back to Queue", callback_data="back_queue")]
                    ]
                    await progress_msg.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await progress_msg.edit_text("✅ Task executed. Use /status to check results.")
                    
            except subprocess.TimeoutExpired:
                await progress_msg.edit_text(f"⏱️ Task still running...\n\n📋 {task_title}\n\nCheck /status in a minute.")
            except Exception as e:
                logging.error(f"Task run error: {e}")
                await progress_msg.edit_text(f"❌ Error running task: {str(e)[:100]}")

        elif data == "task_run_next":
            task = query_one("""
                SELECT * FROM tasks 
                WHERE status IN ('queued', 'pending')
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            """)
            if task:
                execute_sql("UPDATE tasks SET status = 'running', updated_at = NOW() WHERE id = %s", [task['id']])
                task['status'] = 'running'
                msg = render_task_progress(task)
                msg += "\n\n▶️ Task started!"
                keyboard = [[InlineKeyboardButton("← Back to Queue", callback_data="back_queue")]]
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.edit_message_text("📭 No tasks to run!")
                
        elif data == "back_queue":
            # Show queue again
            tasks = query_all("""
                SELECT t.id, t.title, t.priority, t.status, m.phase_number
                FROM tasks t
                LEFT JOIN milestones m ON t.milestone_id = m.id
                WHERE t.status IN ('queued', 'pending')
                ORDER BY t.priority DESC, t.created_at ASC
                LIMIT 10
            """)
            
            if not tasks:
                await query.edit_message_text("📭 No queued tasks!\n\nUse /suggest to generate ideas.")
                return
            
            msg = "🚀 Ready to Run\n\nSelect a task:\n"
            keyboard = []
            
            for t in tasks:
                title = t.get('title', 'Untitled')
                if len(title) > 30:
                    title = title[:27] + "..."
                priority = t.get('priority', 0)
                phase = t.get('phase_number', '-')
                
                btn_text = f"P{priority} | Ph{phase} | {title}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"task_view_{t['id']}")])
            
            keyboard.append([InlineKeyboardButton("▶️ Run Next", callback_data="task_run_next")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(msg, reply_markup=reply_markup)
            
    except Exception as e:
        logging.error(f"Task callback error: {e}")
        try:
            await query.edit_message_text(f"❌ Error: {str(e)}")
        except:
            pass



# ==================== PROJECT SUPPORT ====================
CURRENT_PROJECT_FILE = "/opt/agent-os/.current_project"
# OTP Verification
PENDING_OTP_ACTIONS = {}  # chat_id -> {action, data, expires}

def verify_otp(code: str) -> bool:
    """Verify OTP code"""
    import os
    secret = os.getenv('AGENTOS_TOTP_SECRET')
    if not secret:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)  # Allow 30 sec window

def set_pending_otp(chat_id: int, action: str, data: dict):
    """Store pending OTP action"""
    import time
    PENDING_OTP_ACTIONS[chat_id] = {
        'action': action,
        'data': data,
        'expires': time.time() + 120  # 2 min expiry
    }

def get_pending_otp(chat_id: int):
    """Get and clear pending OTP action"""
    import time
    if chat_id in PENDING_OTP_ACTIONS:
        pending = PENDING_OTP_ACTIONS[chat_id]
        if pending['expires'] > time.time():
            return pending
        del PENDING_OTP_ACTIONS[chat_id]
    return None

def clear_pending_otp(chat_id: int):
    """Clear pending OTP action"""
    if chat_id in PENDING_OTP_ACTIONS:
        del PENDING_OTP_ACTIONS[chat_id]


def get_current_project():
    try:
        if os.path.exists(CURRENT_PROJECT_FILE):
            with open(CURRENT_PROJECT_FILE, 'r') as f:
                return f.read().strip()
    except:
        pass
    return None

def set_current_project(project_name):
    os.makedirs(os.path.dirname(CURRENT_PROJECT_FILE), exist_ok=True)
    with open(CURRENT_PROJECT_FILE, 'w') as f:
        f.write(project_name)

async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all projects"""
    try:
        projects = query_all("""
            SELECT p.name, COUNT(t.id) as total,
                   SUM(CASE WHEN t.status = 'complete' THEN 1 ELSE 0 END) as done,
                   SUM(CASE WHEN t.status IN ('queued','pending') THEN 1 ELSE 0 END) as pending
            FROM projects p LEFT JOIN tasks t ON t.project_id = p.id
            GROUP BY p.id, p.name ORDER BY p.name
        """)
        if not projects:
            await update.message.reply_text("No projects yet. Use /project new <name>")
            return
        current = get_current_project()
        msg = "📁 *Projects*\n\n"
        buttons = []
        for p in projects:
            name = p.get('name', '?')
            done = p.get('done', 0) or 0
            total = p.get('total', 0) or 0
            pending = p.get('pending', 0) or 0
            marker = "👉 " if name == current else "   "
            msg += f"{marker}*{name}* ({done}/{total} done, {pending} pending)\n"
            btn = f"{'✓ ' if name == current else ''}{name}"
            buttons.append([InlineKeyboardButton(btn, callback_data=f"proj_{name}")])
        buttons.append([InlineKeyboardButton("➕ New", callback_data="proj_new_prompt")])
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def project_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Project management"""
    try:
        args = context.args
        if not args:
            current = get_current_project()
            await update.message.reply_text(f"📍 Current: *{current or 'None'}*\n\n/project use <n>\n/project new <n>\n/project delete <n>", parse_mode='Markdown')
            return
        action = args[0].lower()
        if action == "new" and len(args) >= 2:
            name = args[1]
            repo = args[2] if len(args) > 2 else None
            exists = query_one("SELECT id FROM projects WHERE LOWER(name)=LOWER(%s)", [name])
            if exists:
                await update.message.reply_text(f"❌ Already exists: {name}")
                return
            execute_sql("INSERT INTO projects (id,name,status,repo_url,created_at,updated_at) VALUES (gen_random_uuid(),%s,'active',%s,NOW(),NOW())", [name, repo])
            set_current_project(name)
            await update.message.reply_text(f"✅ Created & activated: *{name}*", parse_mode='Markdown')
            return
        if action == "use" and len(args) >= 2:
            name = args[1]
            proj = query_one("SELECT name FROM projects WHERE LOWER(name)=LOWER(%s)", [name])
            if proj:
                set_current_project(proj['name'])
                await update.message.reply_text(f"✅ Switched to: *{proj['name']}*", parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ Not found: {name}")
            return
        if action == "delete" and len(args) >= 2:
            name = args[1]
            proj = query_one("SELECT name FROM projects WHERE LOWER(name)=LOWER(%s)", [name])
            if not proj:
                await update.message.reply_text(f"❌ Not found: {name}")
                return
            # Request OTP
            set_pending_otp(update.effective_chat.id, 'delete_project', {'name': proj['name']})
            await update.message.reply_text(
                f"🔐 *OTP Required*\n\nTo delete *{proj['name']}*, enter your 6-digit OTP code:\n\n(or /cancel to abort)",
                parse_mode='Markdown'
            )
            return
        # Show project details
        proj = query_one("""
            SELECT p.name, COUNT(t.id) as total,
                   SUM(CASE WHEN t.status='complete' THEN 1 ELSE 0 END) as done
            FROM projects p LEFT JOIN tasks t ON t.project_id=p.id
            WHERE LOWER(p.name)=LOWER(%s) GROUP BY p.id
        """, [action])
        if proj:
            done = proj.get('done',0) or 0
            total = proj.get('total',0) or 0
            pct = int(done/total*100) if total else 0
            bar = "▓"*(pct//5) + "░"*(20-pct//5)
            await update.message.reply_text(f"📁 *{proj['name']}*\n{bar} {pct}%\n{done}/{total} tasks done", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Not found: {action}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
# ==================== END PROJECT SUPPORT ====================



async def otp_message_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Filter for OTP messages"""
    handled = await handle_otp_message(update, context)
    # If not handled as OTP, ignore (don't respond to random messages)

async def handle_otp_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle OTP code input"""
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    # Check if it's a 6-digit code
    if not text.isdigit() or len(text) != 6:
        return False
    
    pending = get_pending_otp(chat_id)
    if not pending:
        return False
    
    # Verify OTP
    if not verify_otp(text):
        await update.message.reply_text("❌ Invalid OTP code. Try again or use /cancel")
        return True
    
    # OTP verified - execute pending action
    clear_pending_otp(chat_id)
    action = pending['action']
    data = pending['data']
    
    if action == 'delete_project':
        await execute_project_delete(update, data['name'])
    elif action == 'create_project':
        await execute_project_create(update, data['name'], data.get('repo'))
    
    return True

async def execute_project_delete(update: Update, pname: str):
    """Execute verified project deletion - handles all FK constraints"""
    import asyncio
    import time
    
    try:
        project = query_one("SELECT id FROM projects WHERE name=%s", [pname])
        if not project:
            await update.message.reply_text(f"❌ Project not found: {pname}")
            return
        pid = project['id']
        
        result = query_one("SELECT COUNT(*) as cnt FROM tasks WHERE project_id=%s", [pid])
        task_count = result['cnt'] if result else 0
        
        start_time = time.time()
        
        msg = await update.message.reply_text(f"🗑️ Deleting *{pname}*...\n\n░░░░░░░░░░░░░░░░░░░░ 0%\n⏱️ 0.0s", parse_mode='Markdown')
        await asyncio.sleep(0.15)
        
        # Delete in FK order: suggestions, audit_log, uncertainty_signals, checkpoints, tasks, milestones, project
        
        # 1. suggestions (10%)
        elapsed = time.time() - start_time
        await msg.edit_text(f"🗑️ Deleting *{pname}*...\n\n▓▓░░░░░░░░░░░░░░░░░░ 10%\n⏱️ {elapsed:.1f}s\n\n💡 Removing suggestions...", parse_mode='Markdown')
        execute_sql("DELETE FROM suggestions WHERE task_id IN (SELECT id FROM tasks WHERE project_id=%s)", [pid])
        await asyncio.sleep(0.15)
        
        # 2. audit_log for task checkpoints (20%)
        elapsed = time.time() - start_time
        await msg.edit_text(f"🗑️ Deleting *{pname}*...\n\n▓▓▓▓░░░░░░░░░░░░░░░░ 20%\n⏱️ {elapsed:.1f}s\n\n📝 Removing audit logs...", parse_mode='Markdown')
        execute_sql("DELETE FROM audit_log WHERE checkpoint_id IN (SELECT id FROM checkpoints WHERE task_id IN (SELECT id FROM tasks WHERE project_id=%s) OR project_id=%s)", [pid, pid])
        await asyncio.sleep(0.15)
        
        # 3. uncertainty_signals (30%)
        elapsed = time.time() - start_time
        await msg.edit_text(f"🗑️ Deleting *{pname}*...\n\n▓▓▓▓▓▓░░░░░░░░░░░░░░ 30%\n⏱️ {elapsed:.1f}s\n\n⚠️ Removing uncertainty signals...", parse_mode='Markdown')
        execute_sql("DELETE FROM uncertainty_signals WHERE checkpoint_id IN (SELECT id FROM checkpoints WHERE task_id IN (SELECT id FROM tasks WHERE project_id=%s) OR project_id=%s)", [pid, pid])
        await asyncio.sleep(0.15)
        
        # 4. checkpoints (50%)
        elapsed = time.time() - start_time
        await msg.edit_text(f"🗑️ Deleting *{pname}*...\n\n▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░ 50%\n⏱️ {elapsed:.1f}s\n\n🔖 Removing checkpoints...", parse_mode='Markdown')
        execute_sql("DELETE FROM checkpoints WHERE task_id IN (SELECT id FROM tasks WHERE project_id=%s) OR project_id=%s", [pid, pid])
        await asyncio.sleep(0.15)
        
        # 5. tasks (70%)
        elapsed = time.time() - start_time
        await msg.edit_text(f"🗑️ Deleting *{pname}*...\n\n▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░ 70%\n⏱️ {elapsed:.1f}s\n\n📋 Removing {task_count} tasks...", parse_mode='Markdown')
        execute_sql("DELETE FROM tasks WHERE project_id=%s", [pid])
        await asyncio.sleep(0.15)
        
        # 6. milestones (85%)
        elapsed = time.time() - start_time
        await msg.edit_text(f"🗑️ Deleting *{pname}*...\n\n▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░ 85%\n⏱️ {elapsed:.1f}s\n\n🎯 Removing milestones...", parse_mode='Markdown')
        execute_sql("DELETE FROM milestones WHERE project_id=%s", [pid])
        await asyncio.sleep(0.15)
        
        # 7. project (100%)
        elapsed = time.time() - start_time
        await msg.edit_text(f"🗑️ Deleting *{pname}*...\n\n▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░ 95%\n⏱️ {elapsed:.1f}s\n\n🗂️ Removing project...", parse_mode='Markdown')
        execute_sql("DELETE FROM projects WHERE id=%s", [pid])
        
        if get_current_project() == pname:
            try: os.remove(CURRENT_PROJECT_FILE)
            except: pass
        
        await asyncio.sleep(0.15)
        elapsed = time.time() - start_time
        await msg.edit_text(
            f"✅ *Deleted: {pname}*\n\n▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 100%\n⏱️ {elapsed:.1f}s\n\n📋 {task_count} tasks removed\n🗂️ Project removed",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Delete error: {e}")

async def execute_project_create(update: Update, name: str, repo: str = None):
    """Execute verified project creation"""
    existing = query_one("SELECT id FROM projects WHERE LOWER(name)=LOWER(%s)", [name])
    if existing:
        await update.message.reply_text(f"❌ Already exists: {name}")
        return
    
    execute_sql("INSERT INTO projects (id,name,status,repo_url,created_at,updated_at) VALUES (gen_random_uuid(),%s,'active',%s,NOW(),NOW())", [name, repo])
    set_current_project(name)
    
    msg = f"✅ Created & activated: *{name}*"
    if repo:
        msg += f"\n📦 Repo: {repo}"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def costs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show API cost tracking summary."""
    try:
        import sys
        sys.path.insert(0, '/opt/agent-os-v3/src')
        from cost_tracker import (
            get_today_summary, get_total_costs, get_provider_breakdown, 
            get_daily_costs, get_project_costs, get_operation_costs
        )
        
        args = context.args
        
        if args and args[0].lower() == 'daily':
            daily = get_daily_costs(7)
            msg = "📆 Daily API Costs (Last 7 Days)\n" + "=" * 35 + "\n\n"
            if daily:
                for d in daily:
                    cost = float(d['total_cost_usd'] or 0)
                    calls = int(d['call_count'] or 0)
                    msg += f"{d['date']} | {d['provider']}: ${cost:.4f} ({calls} calls)\n"
            else:
                msg += "No API usage recorded yet.\n"
            await update.message.reply_text(msg)
            return
            
        elif args and args[0].lower() == 'ops':
            ops = get_operation_costs()
            msg = "⚙️ API Costs by Operation\n" + "=" * 35 + "\n\n"
            if ops:
                for op in ops:
                    calls = int(op['call_count'] or 0)
                    total = float(op['total_cost_usd'] or 0)
                    msg += f"{op['operation']} ({op['provider']}): {calls} calls, ${total:.4f}\n"
            else:
                msg += "No API usage recorded yet.\n"
            await update.message.reply_text(msg)
            return
            
        elif args and args[0].lower() == 'projects':
            projects = get_project_costs()
            msg = "📁 API Costs by Project\n" + "=" * 35 + "\n\n"
            if projects:
                for p in projects:
                    name = p['project_name'] or 'Unassigned'
                    calls = int(p['call_count'] or 0)
                    total = float(p['total_cost_usd'] or 0)
                    msg += f"{name} ({p['provider']}): ${total:.4f} ({calls} calls)\n"
            else:
                msg += "No project costs recorded yet.\n"
            await update.message.reply_text(msg)
            return
        
        today = get_today_summary()
        total = get_total_costs()
        providers = get_provider_breakdown()
        
        def safe_val(val, default=0):
            return val if val is not None else default
        
        msg = "💰 API Cost Summary\n" + "=" * 30 + "\n\n"
        msg += "📅 Today:\n"
        msg += f"   Calls: {safe_val(today.get('total_calls'))}\n"
        msg += f"   Tokens: {safe_val(today.get('total_tokens')):,}\n"
        msg += f"   Cost: ${float(safe_val(today.get('total_cost_usd'))):.4f}\n\n"
        msg += "📊 All Time:\n"
        msg += f"   Calls: {safe_val(total.get('total_calls')):,}\n"
        msg += f"   Tokens: {safe_val(total.get('total_tokens')):,}\n"
        msg += f"   Cost: ${float(safe_val(total.get('total_cost_usd'))):.4f}\n\n"
        
        if providers:
            msg += "🏢 By Provider:\n"
            for p in providers:
                msg += f"   {p['provider']}: ${float(safe_val(p['total_cost_usd'])):.4f} ({p['call_count']} calls)\n"
        
        msg += "\n📖 /costs daily | ops | projects"
        await update.message.reply_text(msg)
        
    except Exception as e:
        import traceback
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel pending OTP action"""
    chat_id = update.effective_chat.id
    if get_pending_otp(chat_id):
        clear_pending_otp(chat_id)
        await update.message.reply_text("❌ Cancelled")
    else:
        await update.message.reply_text("Nothing to cancel")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route button callbacks"""
    query = update.callback_query
    data = query.data
    
    if data.startswith("phase_"):
        await phase_callback(update, context)
    elif data == "back_roadmap":
        await back_roadmap_callback(update, context)
    elif data == "expand_all":
        await expand_all_callback(update, context)
    elif data.startswith("sug_"):
        await suggestion_callback(update, context)
    elif data.startswith("task_") or data == "back_queue":
        await task_callback(update, context)
    elif data.startswith("analyze_") or data.startswith("fix_") or data == "back_failed":
        await fix_callback(update, context)
    elif data.startswith("proj_"):
        await query.answer()
        if data == "proj_new_prompt":
            await query.edit_message_text("Use: /project new <name> [repo_url]")
        elif data == "proj_cancel":
            await query.edit_message_text("Cancelled")
        elif data.startswith("proj_del_"):
            pname = data.replace("proj_del_", "")
            execute_sql("DELETE FROM tasks WHERE project_id=(SELECT id FROM projects WHERE name=%s)", [pname])
            execute_sql("DELETE FROM projects WHERE name=%s", [pname])
            if get_current_project() == pname:
                try: os.remove(CURRENT_PROJECT_FILE)
                except: pass
            await query.edit_message_text(f"🗑️ Deleted: {pname}")
        else:
            pname = data.replace("proj_", "")
            set_current_project(pname)
            await query.edit_message_text(f"✅ Switched to: *{pname}*", parse_mode='Markdown')
    else:
        await query.answer("Unknown action")


def main():
    """Initialize and run the Telegram bot"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable must be set")
    
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    app = Application.builder().token(token).build()
    
    # Command handlers
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('start', help_command))
    app.add_handler(CommandHandler('status', status_command))
    app.add_handler(CommandHandler('roadmap', roadmap_command))
    app.add_handler(CommandHandler('tasks', tasks_command))
    app.add_handler(CommandHandler('queue', queue_command))
    app.add_handler(CommandHandler('run', run_command))
    app.add_handler(CommandHandler('suggest', suggest_command))
    app.add_handler(CommandHandler('addphase', addphase_command))
    app.add_handler(CommandHandler('analyze', analyze_command))
    app.add_handler(CommandHandler('refine', refine_command))
    
    # Callback handler for inline buttons
    app.add_handler(CommandHandler('projects', projects_command))
    app.add_handler(CommandHandler('project', project_command))
    app.add_handler(CommandHandler('cancel', cancel_command))
    app.add_handler(CommandHandler('costs', costs_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, otp_message_filter))
    
    print("🤖 Starting Agent-OS v3 Telegram bot...")
    logging.info("Bot started with all commands")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

class IMRPentagonValidator:
    def __init__(self):
        pass
    
    def validate_proposal(self, proposal: dict) -> bool:
        return isinstance(proposal, dict) and ('files_to_create' in proposal or 'files_to_modify' in proposal)
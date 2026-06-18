from projects.models import ProfileLog, ProjectProfile

def evaluate_criteria(stage, profile):
    '''
    Purpose:
        Evaluate all criteria required for a specific maturity stage.

    Input:
        stage   -> Target stage to evaluate.
        profile -> ProjectProfile instance.

    Output:
        {
            "stage": stage,
            "results": [
                {
                    "criterion": str,
                    "value": True | False | None,
                    "domain": str
                }
            ]
        }

    Responsibilities:
        - Check only one stage.
        - Evaluate each criterion independently.
        - Return evidence used for classification.
        - Never determine the final project stage.
        - Never compute scores.
    '''
    pass



def extract_failed_criteria(evidence):
    '''
    Purpose:
        Collect all criteria that failed or were missing during stage evaluation.

    Input:
        evidence -> stage-by-stage evaluation results.

    Output:
        [
            {
                "criterion": str,
                "value": True | False | None,
                "domain": str,
                "stage": str
            }
        ]

    Responsibilities:
        - Scan all evaluated stages.
        - Keep only failed or missing criteria.
        - Preserve stage and domain information.
        - Feed blocker analysis.
    '''

def identify_blockers(failed_criteria):
    '''
    Purpose:
        Group failed or missing criteria into blocker domains.

    Input:
        failed_criteria -> list of failed or missing criteria.

    Output:
        {
            "financier": [...],
            "légal": [...],
            "marché": [...],
            "organisationnel": [...],
            "technique": [...]
        }

    Responsibilities:
        - Group criteria by domain.
        - Rank the strongest blocker domains.
        - Support roadmap retrieval.
    '''



def compute_confidence(evidence):
    '''
    Purpose:
        Estimate how reliable the diagnosis is.

    Input:
        evidence -> full stage evaluation output.

    Output:
        float

    Responsibilities:
        - Increase confidence when more criteria are confirmed.
        - Decrease confidence when many criteria are missing.
        - Return a value between 0 and 1.
    '''

def detect_perception_gap(profile, assigned_stage):
    '''
    Purpose:
        Compare self-assessed stage with diagnosed stage.

    Input:
        profile        -> ProjectProfile instance.
        assigned_stage -> final diagnosed stage.

    Output:
        {
            "gap_size": int,
            "self_assessed_stage": int,
            "diagnosed_stage": int,
            "divergence": bool
        }

    Responsibilities:
        - Compare founder belief to system diagnosis.
        - Measure how far apart the two stages are.
        - Flag divergence clearly.
    '''

def build_diagnostic_metadata(profile, assigned_stage, evidence, blockers, confidence, gap):
    '''
    Purpose:
        Assemble the final diagnostic payload.

    Input:
        profile, assigned_stage, evidence, blockers, confidence, gap

    Output:
        dict

    Responsibilities:
        - Package all diagnostic results into one metadata object.
        - Keep everything traceable.
        - Prepare output for ProfileLog storage.
    '''

def save_diagnostic_log(profile, metadata):
    '''
    Purpose:
        Store the diagnostic result in ProfileLog.

    Input:
        profile   -> ProjectProfile instance.
        metadata  -> diagnostic output dictionary.

    Output:
        ProfileLog instance

    Responsibilities:
        - Append the diagnostic result.
        - Do not overwrite old logs.
        - Preserve traceability and history.
    '''





def diagnose_project(profile):
    '''
    Purpose:
        Generate the final diagnostic assessment.

    Input:
        profile -> ProjectProfile instance.

    Output:
        {
            "author": "diagnostic",
            "metadata": {
                "assigned_stage": str,
                "confidence": float,
                "perception_gap": int,
                "blockers": list,
                "evidence": dict
            }
        }

    Responsibilities:
    should call the whole chain
        - Run stage classification.
        - Compare diagnosed stage with self-assessed stage.
        - Detect perception-reality gaps.
        - Identify blocker domains.
        - Estimate confidence level.
        - Build a traceable diagnostic result.
        - Produce an object ready for ProfileLog storage.
    '''



    


    
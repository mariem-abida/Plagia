from typing import List, Tuple

# Seuils (à adapter charte faculté)
PLAGIAT_OK = 15
PLAGIAT_VERIFY = 20
PLAGIAT_FIX = 30
PLAGIAT_REJECT = 45

AI_OK = 20
AI_VERIFY = 40
AI_REJECT = 60


def decision(plagiarism_percent: float, ai_percent: float) -> Tuple[str, List[str]]:
    """
    Retourne:
      - decision: 'ACCEPTE' | 'A_VERIFIER' | 'A_CORRIGER' | 'REJETE'
      - reasons: liste de raisons
    """
    reasons: List[str] = []

    # 1) Cas REJET immédiat (faculté = stricte)
    if plagiarism_percent >= PLAGIAT_REJECT:
        reasons.append("Plagiat très élevé (>= 45%)")
        return "REJETE", reasons

    if ai_percent >= AI_REJECT:
        reasons.append("Texte généré par IA très probable (>= 60%)")
        return "REJETE", reasons

    # 2) Sinon, calcul décision sur plagiat
    dec = "ACCEPTE"
    if plagiarism_percent >= PLAGIAT_FIX:
        dec = "A_CORRIGER"
        reasons.append("Plagiat élevé (>= 30%)")
    elif plagiarism_percent >= PLAGIAT_VERIFY:
        dec = "A_CORRIGER"
        reasons.append("Plagiat à vérifier (>= 20%)")
    elif plagiarism_percent >= PLAGIAT_OK:
        dec = "A_VERIFIER"
        reasons.append("Similarité modérée (>= 15%)")

    # 3) IA aggrave (mais pas rejet ici car déjà traité)
    if ai_percent >= AI_VERIFY:
        reasons.append("Utilisation probable d’IA (>= 40%)")
        if dec == "ACCEPTE":
            dec = "A_VERIFIER"
    elif ai_percent >= AI_OK:
        reasons.append("Utilisation possible d’IA (>= 20%)")

    # 4) Si aucune raison
    if not reasons:
        reasons.append("Niveaux acceptables (plagiat & IA)")

    return dec, reasons

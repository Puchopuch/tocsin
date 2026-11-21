"""What a flaw is and what it allows, read from the words of the source with fixed tables, in
French and in English. No AI: a word that is not in a table gives nothing, and the card then says
less ("Non communiqué") rather than something invented.

- The type of a CISA flaw comes from the name the CISA gives it (its words are those of the CWE
  titles), or else from its CWE numbers (field `cwes`).
- Its consequence, and who can exploit it, come from the description of the CISA, in the
  sentence where the consequence is written.
- The risks and the affected systems of a CERT-FR alert come from the lists of its page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .text import fold

# Types of flaws, by CWE number: (French, English), 45 characters at most in both.
CWE_TYPES = {
    "CWE-20": ("Validation d'entrée insuffisante", "Improper input validation"),
    "CWE-22": ("Traversée de répertoires", "Path traversal"),
    "CWE-23": ("Traversée de répertoires", "Path traversal"),
    "CWE-24": ("Traversée de répertoires", "Path traversal"),
    "CWE-29": ("Traversée de répertoires", "Path traversal"),
    "CWE-35": ("Traversée de répertoires", "Path traversal"),
    "CWE-36": ("Traversée de répertoires", "Path traversal"),
    "CWE-59": ("Suivi de lien symbolique", "Link following"),
    "CWE-73": ("Chemin de fichier contrôlé de l'extérieur", "External control of a file path"),
    "CWE-77": ("Injection de commandes", "Command injection"),
    "CWE-78": ("Injection de commandes système", "OS command injection"),
    "CWE-79": ("Script intersite (XSS)", "Cross-site scripting (XSS)"),
    "CWE-88": ("Injection d'arguments", "Argument injection"),
    "CWE-89": ("Injection SQL", "SQL injection"),
    "CWE-91": ("Injection XML", "XML injection"),
    "CWE-94": ("Injection de code", "Code injection"),
    "CWE-95": ("Injection de code", "Code injection"),
    "CWE-98": ("Inclusion de fichier distant", "Remote file inclusion"),
    "CWE-116": ("Encodage de sortie incorrect", "Improper output encoding"),
    "CWE-119": ("Corruption de mémoire", "Memory corruption"),
    "CWE-120": ("Débordement de tampon", "Buffer overflow"),
    "CWE-121": ("Débordement de tampon de pile", "Stack-based buffer overflow"),
    "CWE-122": ("Débordement de tampon de tas", "Heap-based buffer overflow"),
    "CWE-125": ("Lecture hors limites", "Out-of-bounds read"),
    "CWE-134": ("Chaîne de format non contrôlée", "Uncontrolled format string"),
    "CWE-140": ("Délimiteurs mal neutralisés", "Improper neutralization of delimiters"),
    "CWE-190": ("Dépassement d'entier", "Integer overflow"),
    "CWE-200": ("Divulgation d'informations", "Information disclosure"),
    "CWE-250": ("Exécution avec trop de privilèges", "Execution with unnecessary privileges"),
    "CWE-259": ("Mot de passe codé en dur", "Hard-coded password"),
    "CWE-269": ("Gestion des privilèges incorrecte", "Improper privilege management"),
    "CWE-276": ("Permissions par défaut incorrectes", "Incorrect default permissions"),
    "CWE-284": ("Contrôle d'accès défaillant", "Improper access control"),
    "CWE-285": ("Autorisation incorrecte", "Improper authorization"),
    "CWE-287": ("Authentification défaillante", "Improper authentication"),
    "CWE-288": ("Contournement d'authentification", "Authentication bypass"),
    "CWE-290": ("Contournement d'authentification", "Authentication bypass by spoofing"),
    "CWE-294": ("Rejeu pour contourner l'authentification", "Authentication bypass by capture-replay"),
    "CWE-295": ("Validation de certificat incorrecte", "Improper certificate validation"),
    "CWE-306": ("Fonction critique sans authentification", "Critical function without authentication"),
    "CWE-307": ("Tentatives de connexion illimitées", "Unlimited login attempts"),
    "CWE-319": ("Données sensibles transmises en clair", "Sensitive data sent in cleartext"),
    "CWE-345": ("Authenticité des données non vérifiée", "Data authenticity not verified"),
    "CWE-347": ("Signature mal vérifiée", "Improper signature verification"),
    "CWE-352": ("Falsification de requête intersite (CSRF)", "Cross-site request forgery (CSRF)"),
    "CWE-362": ("Situation de concurrence", "Race condition"),
    "CWE-400": ("Consommation de ressources illimitée", "Uncontrolled resource consumption"),
    "CWE-416": ("Utilisation de mémoire libérée", "Use after free"),
    "CWE-420": ("Canal alternatif non protégé", "Unprotected alternate channel"),
    "CWE-426": ("Chemin de recherche non fiable", "Untrusted search path"),
    "CWE-427": ("Chemin de recherche non contrôlé", "Uncontrolled search path"),
    "CWE-434": ("Envoi de fichier dangereux", "Unrestricted upload of a dangerous file"),
    "CWE-470": ("Réflexion non sûre", "Unsafe reflection"),
    "CWE-476": ("Déréférencement de pointeur nul", "NULL pointer dereference"),
    "CWE-502": ("Désérialisation de données non fiables", "Deserialization of untrusted data"),
    "CWE-552": ("Fichiers accessibles à des tiers", "Files accessible to external parties"),
    "CWE-601": ("Redirection ouverte", "Open redirect"),
    "CWE-611": ("Entité externe XML (XXE)", "XML external entity (XXE)"),
    "CWE-639": ("Contournement d'autorisation par clé (IDOR)", "Authorization bypass via user key (IDOR)"),
    "CWE-668": ("Ressource exposée à des tiers", "Resource exposed to the wrong sphere"),
    "CWE-693": ("Mécanisme de protection défaillant", "Protection mechanism failure"),
    "CWE-732": ("Permissions mal attribuées", "Incorrect permission assignment"),
    "CWE-770": ("Ressources allouées sans limite", "Allocation of resources without limits"),
    "CWE-787": ("Écriture hors limites", "Out-of-bounds write"),
    "CWE-798": ("Identifiants codés en dur", "Hard-coded credentials"),
    "CWE-822": ("Pointeur non fiable déréférencé", "Untrusted pointer dereference"),
    "CWE-843": ("Confusion de type", "Type confusion"),
    "CWE-862": ("Autorisation manquante", "Missing authorization"),
    "CWE-863": ("Autorisation incorrecte", "Incorrect authorization"),
    "CWE-912": ("Fonction cachée", "Hidden functionality"),
    "CWE-917": ("Injection de langage d'expression", "Expression language injection"),
    "CWE-918": ("Falsification de requête côté serveur (SSRF)", "Server-side request forgery (SSRF)"),
    "CWE-943": ("Injection de requête de données", "Data query injection"),
    "CWE-1321": ("Pollution de prototype", "Prototype pollution"),
    "CWE-1336": ("Injection de modèle", "Template injection"),
}

# Words of the names the CISA gives, and the CWE they name. The most precise first.
NAME_TYPES = (
    ("os command injection", "CWE-78"),
    ("command injection", "CWE-77"),
    ("argument injection", "CWE-88"),
    ("sql injection", "CWE-89"),
    ("expression language injection", "CWE-917"),
    ("template injection", "CWE-1336"),
    ("code injection", "CWE-94"),
    ("eval injection", "CWE-95"),
    ("xml injection", "CWE-91"),
    ("special elements in data query logic", "CWE-943"),
    ("path traversal", "CWE-22"),
    ("directory traversal", "CWE-22"),
    ("deserialization of untrusted data", "CWE-502"),
    ("authentication bypass by capture-replay", "CWE-294"),
    ("authentication bypass by spoofing", "CWE-290"),
    ("authentication bypass", "CWE-288"),
    ("missing authentication", "CWE-306"),
    ("improper authentication", "CWE-287"),
    ("hard-coded credentials", "CWE-798"),
    ("hard-coded password", "CWE-259"),
    ("cross-site scripting", "CWE-79"),
    ("cross-site request forgery", "CWE-352"),
    ("server-side request forgery", "CWE-918"),
    ("use-after-free", "CWE-416"),
    ("use after free", "CWE-416"),
    ("out-of-bounds write", "CWE-787"),
    ("out-of-bounds read", "CWE-125"),
    ("heap-based buffer overflow", "CWE-122"),
    ("stack-based buffer overflow", "CWE-121"),
    ("buffer overflow", "CWE-120"),
    ("integer overflow", "CWE-190"),
    ("type confusion", "CWE-843"),
    ("null pointer dereference", "CWE-476"),
    ("memory corruption", "CWE-119"),
    ("race condition", "CWE-362"),
    ("missing authorization", "CWE-862"),
    ("incorrect authorization", "CWE-863"),
    ("improper authorization", "CWE-285"),
    ("improper privilege management", "CWE-269"),
    ("incorrect permission assignment", "CWE-732"),
    ("incorrect default permissions", "CWE-276"),
    ("improper access control", "CWE-284"),
    ("unrestricted upload", "CWE-434"),
    ("unsafe reflection", "CWE-470"),
    ("unprotected alternate channel", "CWE-420"),
    ("neutralization of delimiters", "CWE-140"),
    ("encoding or escaping of output", "CWE-116"),
    ("xml external entit", "CWE-611"),
    ("open redirect", "CWE-601"),
    ("link following", "CWE-59"),
    ("untrusted search path", "CWE-426"),
    ("uncontrolled search path", "CWE-427"),
    ("certificate validation", "CWE-295"),
    ("hidden functionality", "CWE-912"),
    ("prototype pollution", "CWE-1321"),
    ("information disclosure", "CWE-200"),
    ("exposure of sensitive information", "CWE-200"),
    ("improper input validation", "CWE-20"),
)


def flaw_type(name: str, cwes: list[str]) -> tuple[str, str] | None:
    """The type of a flaw, (French, English): from its name, else from its first known CWE."""
    folded = fold(name)
    for words, cwe in NAME_TYPES:
        if words in folded:
            return CWE_TYPES[cwe]
    return next((CWE_TYPES[cwe] for cwe in cwes if cwe in CWE_TYPES), None)


# What a flaw allows, from the most serious to the least.


@dataclass(frozen=True)
class Impact:
    key: str
    label: tuple[str, str]  # the "Impact" line, (French, English)
    remote_label: tuple[str, str] | None  # the same, when the source says it works remotely
    verb: tuple[str, str]  # what an attacker can do, for the summary


IMPACTS = (
    (r"\bexecut\w*\s+(?:arbitrary\s+|malicious\s+)?(?:code|javascript)\b|\bcode execution\b",
     Impact("code", ("Exécution de code", "Code execution"), ("Exécution de code à distance", "Remote code execution"),
            ("exécuter du code", "run code"))),
    (r"\bexecut\w*\s+(?:arbitrary\s+|os\s+|system\s+|shell\s+)?commands?\b|\bcommands?\s+(?:that|which)\s+(?:are|is)\s+execut\w*|\bcommand execution\b",
     Impact("commands", ("Exécution de commandes", "Command execution"),
            ("Exécution de commandes à distance", "Remote command execution"), ("exécuter des commandes", "run commands"))),
    (r"\bexecut\w*\s+as\s+(?:root|system|administrator)\b|\bwith\s+(?:root|system)\s+privileges\b|\bescalat\w*\s+(?:\w+\s+)?privileges?\b"
     r"|\bprivilege escalation\b|\belevat\w*\s+(?:\w+\s+)?privileges?\b|\bgain\w*\s+(?:root|system|administrat\w*|admin|elevated)\s+(?:privileges|access|rights)\b",
     Impact("privileges", ("Élévation de privilèges", "Privilege escalation"), None,
            ("obtenir des droits plus élevés", "gain higher privileges"))),
    (r"\bbypass\w*\s+authentication\b|\bauthentication bypass\b|\bunauthori[sz]ed access\b|\btake\s*over\b|\btakeover\b",
     Impact("access", ("Accès non autorisé au système", "Unauthorized access to the system"), None,
            ("accéder au système sans autorisation", "access the system without authorization"))),
    (r"\bbypass\w*\s+(?:a\s+|the\s+)?(?:security\s+features?|security\s+restrictions?|protections?|pointer authentication|sandbox|mitigations?)\b",
     Impact("bypass", ("Contournement d'une protection", "Protection bypass"), None,
            ("contourner une protection", "get around a protection"))),
    (r"\b(?:disclos|read|access|obtain|leak)\w*\b[^.]{0,40}?\b(?:or|and)\s+modif\w*",
     Impact("data_rw", ("Lecture ou modification de données", "Reading or changing data"), None,
            ("lire ou modifier des données", "read or change data"))),
    (r"\bdisclos\w*|\binformation disclosure\b|\bread\s+(?:arbitrary\s+)?(?:files|data|memory)\b"
     r"|\bobtain\w*\s+(?:sensitive\s+)?(?:information|data|credentials)\b|\bleak\w*|\bexfiltrat\w*|\baccess\w*\s+sensitive\b",
     Impact("data", ("Fuite de données", "Data leak"), None, ("lire des données protégées", "read protected data"))),
    (r"\b(?:write|upload|create|delete|overwrite)\w*\s+(?:arbitrary\s+)?files?\b",
     Impact("files", ("Écriture ou suppression de fichiers", "Writing or deleting files"), None,
            ("écrire ou supprimer des fichiers", "write or delete files"))),
    (r"\bdenial[- ]of[- ]service\b|\bcrash\w*|\bexhaust\w*",
     Impact("dos", ("Déni de service", "Denial of service"), None,
            ("rendre le service indisponible", "make the service unavailable"))),
    (r"\binject\w*\s+(?:arbitrary\s+)?(?:web\s+)?scripts?\b|\bcross-site scripting\b",
     Impact("xss", ("Script injecté dans des pages web", "Script injected into web pages"), None,
            ("injecter du script dans des pages web", "inject script into web pages"))),
)
REMOTE = re.compile(r"\bremote(?:ly)?\b|\bnetwork access\b|\bover (?:a|the) network\b|\bnetwork attackers?\b", re.IGNORECASE)
# Who can exploit the flaw: the one the flaw "allows" to act, or the subject of the sentence
# ("An authenticated local user can..."); never a user named elsewhere ("as the service user").
ACTOR = re.compile(
    r"(?:\b(?:allow|enable|let|permit)\w*\s+|^)(?:(?:an?|any|the)\s+)?"
    r"(?P<adjectives>(?:(?:unauthenticated|unauthori[sz]ed|authenticated|remote|local|network|low-privileged)[\s,]+)*)"
    r"(?P<noun>attackers?|users?|threat actors?)\b",
    re.IGNORECASE,
)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


@dataclass(frozen=True)
class Consequence:
    """What the description says a flaw allows, and who can use it."""

    label: tuple[str, str]
    verb: tuple[str, str]
    who: tuple[str, str]


def who_can(sentence: str, remote: bool) -> tuple[str, str]:
    """"un attaquant à distance, sans compte," / "a remote attacker without an account"."""
    actor = ACTOR.search(sentence)
    adjectives = fold(actor["adjectives"]) if actor else ""
    user = bool(actor) and fold(actor["noun"]).startswith("user")
    unauthenticated = "unauthenticated" in adjectives
    unauthorized = "unauthori" in adjectives and not unauthenticated
    authenticated = re.search(r"(?<!un)authenticated", adjectives) is not None
    local = "local" in adjectives
    remote = remote or "remote" in adjectives or "network" in adjectives

    head = "un utilisateur" if user else "un attaquant"
    head += " local" if local else ""
    head += " connecté" if authenticated and user else ""
    after = [
        *(["à distance"] if remote else []),
        *(["sans compte"] if unauthenticated else []),
        *(["non autorisé"] if unauthorized else []),
        *(["disposant d'un compte"] if authenticated and not user else []),
    ]
    fr = head + (f" {after[0]}" if after else "") + "".join(f", {part}" for part in after[1:]) + ("," if len(after) > 1 else "")

    words = [
        *(["unauthorized"] if unauthorized else []),
        *(["logged-in"] if authenticated else []),
        *(["local"] if local else []),
        *(["remote"] if remote else []),
        "user" if user else "attacker",
    ]
    # "an attacker", "an unauthorized...", but "a user", "a local...", "a remote...".
    article = "an" if words[0][0] in "aeio" or words[0].startswith("un") else "a"
    en = f"{article} {' '.join(words)}" + (" without an account" if unauthenticated else "")
    return fr, en


def consequence(description: str) -> Consequence | None:
    """The most serious consequence the description names, and who can cause it, read in the
    sentence that names it. None when no word of the table is there."""
    for pattern, impact in IMPACTS:
        match = re.search(pattern, description, re.IGNORECASE)
        if not match:
            continue
        sentence = next(
            (part for part in SENTENCE.split(description) if match.group(0) in part), description
        )
        remote = REMOTE.search(sentence) is not None
        label = impact.remote_label if remote and impact.remote_label else impact.label
        return Consequence(label=label, verb=impact.verb, who=who_can(sentence, remote))
    return None


# CERT-FR: the risks of an alert, from the most serious, and their English.
CERTFR_RISKS = (
    ("Exécution de code arbitraire à distance", "Remote arbitrary code execution"),
    ("Exécution de code arbitraire", "Arbitrary code execution"),
    ("Élévation de privilèges", "Privilege escalation"),
    ("Contournement de la politique de sécurité", "Security policy bypass"),
    ("Atteinte à la confidentialité des données", "Breach of data confidentiality"),
    ("Atteinte à l'intégrité des données", "Breach of data integrity"),
    ("Usurpation d'identité", "Identity spoofing"),
    ("Injection de code indirecte à distance (XSS)", "Cross-site scripting (XSS)"),
    ("Injection de requêtes illégitimes par rebond (CSRF)", "Cross-site request forgery (CSRF)"),
    ("Falsification de requêtes côté serveur (SSRF)", "Server-side request forgery (SSRF)"),
    ("Déni de service à distance", "Remote denial of service"),
    ("Déni de service", "Denial of service"),
)
RISK_LABELS = {
    "Injection de code indirecte à distance (XSS)": "Injection de code indirecte (XSS)",
    "Injection de requêtes illégitimes par rebond (CSRF)": "Requêtes illégitimes par rebond (CSRF)",
}


def same_words(a: str, b: str) -> bool:
    return " ".join(fold(a).replace("’", "'").split()) == " ".join(fold(b).replace("’", "'").split())


def known_risks(risks: list[str]) -> list[tuple[str, str]]:
    """The risks of the alert that the table knows, from the most serious: (French, English). The
    French label is shortened when needed to fit the "Impact" line."""
    return [
        (RISK_LABELS.get(fr, fr), en)
        for fr, en in CERTFR_RISKS
        if any(same_words(fr, risk) for risk in risks)
    ]


VERSION_WORDS = re.compile(
    r"\s+(?:versions?\b|toutes\b|sans\b|antérieures?\b|postérieures?\b|pour\b|jusqu|à partir|\(|\d+\.(?:\d|x))",
    re.IGNORECASE,
)


def product_names(systems: list[str]) -> list[str]:
    """The products of the list "Systèmes affectés", without their versions, each once:
    "NGINX Open Source versions 1.31.x antérieures à 1.31.9" gives "NGINX Open Source"."""
    names: list[str] = []
    for system in systems:
        name = VERSION_WORDS.split(system, maxsplit=1)[0].strip(" ,;:")
        if name and name not in names:
            names.append(name)
    return names

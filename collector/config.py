"""Settings of the collector: paths, sources, politeness, limits, and the lists the code uses to
judge an entry (widespread software, consumer products, signs of a person's name)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "frontend" / "public" / "data" / "cards.json"
STATE_PATH = ROOT / "collector" / "state.db"
JOURNAL_PATH = ROOT / "collector" / "logs" / "collector.log"
ENV_PATH = ROOT / ".env"

# Politeness (B4). The repository URL joins the User-Agent once the repository is public: until
# then it would only show the owner's account and lead to a missing page.
USER_AGENT = "Tocsin-collecteur/0.1"
TIMEOUT_SECONDS = 20.0
SECONDS_BETWEEN_REQUESTS = 1.0  # to the same site

WINDOW_DAYS = 7
TRACKED_COUNTRIES = ("FR",)

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
CERTFR_FEED_URL = "https://cert.cyber.gouv.fr/alerte/feed/"
CERTFR_HOST = "cert.cyber.gouv.fr"
RANSOMWARE_LIVE_API = "https://api-pro.ransomware.live"
RANSOMWARE_LIVE_HOST = "ransomware.live"
RANSOMWARE_LIVE_KEY = "RANSOMWARE_LIVE_API_KEY"

# Lengths of frontend/README.md (B5 rule 5).
MAX_TITLE_WORDS = 10
MAX_SHORT = 45  # victim, method, loot
MAX_LINE = 75  # am_i_affected, action

# Widespread software (B6): a flaw already exploited in one of them is "grave". The list of the
# brief, plus Check Point (firewalls as common as Fortinet or Palo Alto Networks) and Synology and
# QNAP (network storage very common in small businesses). The CISA now files VMware under
# Broadcom. Apache publishes hundreds of programs, so only its most used ones count.
WIDESPREAD_VENDORS = frozenset({
    "microsoft", "apple", "google", "mozilla", "cisco", "fortinet", "ivanti", "citrix", "vmware",
    "palo alto networks", "oracle", "adobe", "sap", "atlassian", "sonicwall", "juniper", "f5",
    "linux", "check point", "synology", "qnap",
})
WIDESPREAD_PRODUCTS = {"apache": ("http server", "tomcat", "log4j"), "broadcom": ("vmware",)}

# Consumer products: when the source names one, the general public is concerned too. Each rule is
# (vendor or None, product or None). A vendor, when given, must be named as well, so that Cisco
# IOS is not taken for Apple iOS; a vendor without product covers everything it makes. Deduced
# from the product named by the source only.
CONSUMER_PRODUCTS = (
    # Browsers
    ("google", "chrome"), ("google", "chromium"), (None, "firefox"), ("apple", "safari"),
    ("apple", "webkit"), ("microsoft", "edge"),
    # Systems of computers and phones
    ("microsoft", "windows"), ("apple", "macos"), ("apple", "ios"), ("apple", "ipados"),
    (None, "android"),
    # Common apps
    (None, "whatsapp"), (None, "telegram"), ("signal", "signal"), (None, "zoom"),
    ("microsoft", "office"), ("microsoft", "word"), ("microsoft", "excel"),
    ("microsoft", "outlook"), ("adobe", "acrobat"), ("adobe", "reader"), (None, "winrar"),
    (None, "7-zip"), (None, "vlc"), ("apple", "itunes"), (None, "thunderbird"),
    # Equipment found at home: network storage, boxes and routers, media server
    ("synology", None), ("qnap", None), ("western digital", "my cloud"),
    ("tp-link", None), ("d-link", None), ("netgear", None), ("asus", None), ("asustek", None),
    ("linksys", None), ("tenda", None), (None, "livebox"), (None, "freebox"), (None, "bbox"),
    ("plex", "media server"),
)
NOT_CONSUMER = ("windows server",)

# Signs that a victim name is a person's (B5 rule 7). Without AI the code cannot be sure, so in
# doubt the claim is held back, and its name goes to the local journal only.
PERSON_TITLES = frozenset(
    "dr docteur maitre me mme madame monsieur mr mrs ms pr professeur".split()
)
ORGANISATION_WORDS = frozenset("""
    sa sas sasu sarl eurl sci scop snc gie selarl inc llc ltd plc gmbh ag bv nv spa srl sl co
    corp corporation company compagnie group groupe groupement holding societe entreprise
    entreprises industrie industries international services solutions systems systemes
    technologies technology consulting conseil logistique logistics transport transports
    immobilier construction constructions btp batiment energie energy avocats notaires notaire
    expertise comptable comptables assurance assurances banque bank mutuelle hotel hotels
    restaurant pharmacie laboratoire laboratoires clinique clinic hopital hospital chu ehpad
    cabinet mairie ville commune communaute agglomeration departement region prefecture
    universite university ecole school lycee college institut institute centre center fondation
    foundation association federation syndicat chambre ministere agence agency office club
    studio atelier garage automobiles distribution france
""".split())
FIRST_NAMES = frozenset("""
    adam adrien agnes ahmed alain alexandre alexis ali alice amandine amelie amina anais andre
    andrea anne anna anthony antoine arnaud arthur audrey aurelie axel baptiste beatrice benjamin
    bernard brigitte bruno camille carole caroline catherine cecile cedric celine chantal charles
    charlotte chloe christian christiane christine christophe claire clara claude clement colette
    corentin corinne cyril damien daniel david delphine denis denise didier dominique dylan
    elisabeth elodie emilie emma emmanuel enzo eric ethan eva fabien fabrice fanny fatima
    florence florian francis francoise franck francois frederic gabriel gaelle georges gerard
    gilles gregory guillaume guy helene henri herve hugo ines isabelle jacqueline jacques jade
    jean jeanne jerome jeremy joseph josiane jules julie julien juliette justine karim karine
    kevin laetitia laura laurence laurent lea leila leo lina loic louis louise luc lucas lucie
    ludovic madeleine manon marc marcel margaux marie marine marion martin martine mathieu
    mathilde matthieu maxime mehdi melanie michel michele mickael mohamed monique nadia nadine
    nathalie nathan nicolas nicole nina noah oceane odile olivier patrice
    patricia patrick paul pauline philippe pierre quentin rachid raphael raymond rene richard
    robert roger romain rose sabrina samuel sandra sandrine sarah sebastien serge severine simon
    simone sophie stephane stephanie suzanne sylvain sylvie theo thierry thomas valentin
    valerie vanessa veronique victor vincent virginie xavier yann yannick yves yvette youssef zoe
    andrew ashley barbara brian christopher donna edward elizabeth emily george james jennifer
    jessica john karen kenneth linda lisa margaret mark mary matthew michael nancy peter rebecca
    ronald ryan scott steven susan timothy william
""".split())

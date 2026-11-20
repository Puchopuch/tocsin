"""Phase 1 cards (B6): each template and its generic variants, the CERT-FR rules, the claims, the
general public deduced from the product, the names held back and the safety net."""

from datetime import date, datetime, timezone

from collector import cards, severity
from collector.models import CertfrAlert, KevEntry
from collector.sources import certfr, kev, ransomware_live

from .helpers import NOW, sample

ENTRIES = {entry.cve: entry for entry in kev.parse(sample("kev.json"))}
ALERTS = {alert.number: alert for alert in certfr.parse(sample("certfr-alertes.xml"))}
CLAIMS = {
    claim.victim: claim
    for claim in ransomware_live.recent(ransomware_live.parse(sample("ransomware_live.json")), NOW)
}


def card_for(cve: str) -> dict:
    return cards.kev_card(ENTRIES[cve])


# CISA


def test_kev_widespread_software_is_grave():
    card = card_for("CVE-2024-10441")  # Synology DiskStation Manager (DSM)
    assert card["severity"] == "grave"
    assert card["severity_reason"] == "Faille déjà exploitée dans un logiciel répandu."
    assert card["title"] == "Faille exploitée dans Synology DSM"
    assert card["victim"] == {"label": "Utilisateurs de Synology DSM", "status": "confirme"}
    assert card["am_i_affected"] == "Oui, si vous utilisez Synology DSM sans la dernière mise à jour."
    assert card["action"] == "Installez la mise à jour de sécurité de Synology sans attendre."
    assert card["audience"] == "les_deux"  # a NAS, found at home too
    assert card["first_seen"] == "2026-11-18"
    assert card["summary"][0].startswith("La CISA, l'agence américaine de cybersécurité, a ajouté cette faille de Synology DiskStation Manager (DSM)")
    assert card["technical"]["software"] == ["Synology DiskStation Manager (DSM)"]


def test_kev_less_common_software_is_significant():
    card = card_for("CVE-2026-40217")  # BerriAI LiteLLM
    assert card["severity"] == "significative"
    assert card["severity_reason"] == "Faille déjà exploitée, dans un logiciel peu répandu."
    assert card["title"] == "Faille exploitée dans BerriAI LiteLLM"
    assert card["victim"]["label"] == "Utilisateurs de BerriAI LiteLLM"
    assert card["am_i_affected"] == "Oui, si vous utilisez BerriAI LiteLLM sans la dernière mise à jour."
    assert card["method"] == "Faille déjà exploitée par des attaquants"
    assert card["loot"] == "Accès possible aux systèmes non mis à jour"


def test_kev_uses_the_short_name_in_brackets():
    card = card_for("CVE-2026-90817")  # Vanderbilt University, Research Electronic Data Capture (REDCap)
    assert card["title"] == "Faille exploitée dans REDCap"
    assert card["victim"]["label"] == "Utilisateurs de REDCap"
    assert card["am_i_affected"] == "Oui, si vous utilisez REDCap sans la dernière mise à jour."
    assert card["action"] == "Installez la dernière mise à jour de sécurité sans attendre."
    assert "Research Electronic Data Capture (REDCap)" in card["summary"][0]


def test_only_an_abbreviation_counts_as_a_short_name():
    assert cards.short_name("Synology", "DiskStation Manager (DSM)") == "DSM"
    assert cards.short_name("Vanderbilt University", "Research Electronic Data Capture (REDCap)") == "REDCap"
    assert cards.short_name("Ivanti", "Connect Secure (ICS)") == "ICS"
    assert cards.short_name("Microsoft", "Edge (Chromium-based)") is None
    assert cards.short_name("Microsoft", "Windows (Multiple Versions)") is None
    assert cards.short_name("Exemple", "Passerelle (v2)") is None
    assert cards.product_name("Ivanti", "Connect Secure (ICS)") == "Ivanti ICS"
    assert cards.product_name("Microsoft", "Edge (Chromium-based)") == "Microsoft Edge (Chromium-based)"


def test_kev_long_names_fall_back_on_the_generic_sentences():
    product = "Plateforme De Gestion Des Rendez-Vous En Ligne Pour Cabinets"
    entry = KevEntry(cve="CVE-2099-0003", vendor="Éditeur Imaginaire Long", product=product, date_added=date(2026, 11, 18))
    card = cards.kev_card(entry)
    assert card["victim"]["label"] == "Utilisateurs de ce logiciel"
    assert card["am_i_affected"] == "Oui, si vous utilisez ce logiciel sans la dernière mise à jour."
    assert card["action"] == "Installez la dernière mise à jour de sécurité sans attendre."
    assert len(card["title"].split()) <= 10


def test_kev_title_falls_back_on_the_vendor_then_on_a_generic_title():
    product = "Un Produit Au Nom Vraiment Beaucoup Trop Long Pour Un Titre"
    entry = KevEntry(cve="CVE-2099-0001", vendor="Exemple", product=product, date_added=date(2026, 11, 18))
    assert cards.kev_card(entry)["title"] == "Faille exploitée dans un logiciel d'Exemple"
    entry = entry.model_copy(update={"vendor": "Un Éditeur Au Nom Vraiment Beaucoup Trop Long"})
    assert cards.kev_card(entry)["title"] == "Faille exploitée dans un logiciel"


def test_kev_elision_before_a_vowel():
    card = card_for("CVE-2026-90436")  # Apache Axis
    assert card["victim"]["label"] == "Utilisateurs d'Apache Axis"
    assert card["action"] == "Installez la mise à jour de sécurité d'Apache sans attendre."
    assert card["severity"] == "significative"  # not one of Apache's widespread programs


def test_kev_widespread_programs_and_ransomware_use():
    card = card_for("CVE-2021-45046")  # Apache Log4j2, used by ransomware
    assert card["severity"] == "grave"
    assert card["summary"][0].endswith("Elle sert déjà dans des attaques par rançongiciel, selon la CISA.")
    assert card_for("CVE-2026-59310")["severity"] == "grave"  # VMware, filed under Broadcom
    assert card_for("CVE-2026-123039")["severity"] == "grave"  # Check Point


def test_kev_summary_timeline_sources():
    card = card_for("CVE-2026-40217")
    assert card["summary"] == [
        "La CISA, l'agence américaine de cybersécurité, a ajouté cette faille de BerriAI LiteLLM "
        "à sa liste des failles exploitées le 18 novembre 2026."
    ]
    assert card["timeline"] == [
        {"date": "2026-11-18", "label": "Ajout à la liste des failles exploitées de la CISA"},
        {"date": "2026-12-02", "label": "Date limite de correction pour les administrations américaines"},
    ]
    assert card["sources"] == [
        {
            "name": "CISA",
            "title": "Catalogue des failles exploitées : CVE-2026-40217",
            "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext=CVE-2026-40217",
            "official": True,
        },
        {
            "name": "NVD",
            "title": "Fiche CVE-2026-40217",
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2026-40217",
            "official": True,
        },
    ]
    assert card["attacker"] == {"name": None, "country": None, "status": "inconnu", "source": None}
    assert card["technical"] == {"cves": ["CVE-2026-40217"], "software": ["BerriAI LiteLLM"], "techniques": []}


def test_kev_multiple_products_use_the_vendor():
    card = card_for("CVE-2024-27834")  # Apple, "Multiple Products"
    assert card["title"] == "Faille exploitée dans des produits Apple"
    assert card["victim"]["label"] == "Utilisateurs de produits Apple"
    assert card["am_i_affected"] == "Oui, si vous utilisez un produit Apple sans la dernière mise à jour."


def test_consumer_products_reach_the_general_public():
    assert card_for("CVE-2026-96951")["audience"] == "les_deux"  # Microsoft Windows
    assert card_for("CVE-2026-125350")["audience"] == "les_deux"  # Google Chromium
    assert card_for("CVE-2024-27834")["audience"] == "les_deux"  # Apple, products named in the source
    assert card_for("CVE-2010-3765")["audience"] == "les_deux"  # Mozilla, Firefox named in the source
    assert card_for("CVE-2026-40217")["audience"] == "entreprises"


def test_equipment_found_at_home_reaches_the_general_public():
    def audience(vendor, product):
        entry = KevEntry(cve="CVE-2099-0004", vendor=vendor, product=product, date_added=date(2026, 11, 18))
        return cards.kev_card(entry)["audience"]

    assert audience("QNAP", "QTS") == "les_deux"
    assert audience("TP-Link", "Archer AX21 Routers") == "les_deux"
    assert audience("D-Link", "DIR-859 Router") == "les_deux"
    assert audience("NETGEAR", "Nighthawk Routers") == "les_deux"
    assert audience("ASUS", "RT-AX55 Routers") == "les_deux"
    assert audience("Plex", "Media Server") == "les_deux"
    assert audience("Western Digital", "My Cloud") == "les_deux"
    assert audience("Exemple", "Serveur de fichiers") == "entreprises"


def test_cisco_ios_is_not_apple_ios():
    card = card_for("CVE-2008-4128")
    assert card["audience"] == "entreprises"
    assert card["severity"] == "grave"


# CERT-FR


def test_certfr_card():
    card = cards.certfr_card(ALERTS["CERTFR-2026-ALE-017"])
    assert card["id"] == "certfr-2026-ALE-017"
    assert card["title"] == "Multiples vulnérabilités dans F5 NGINX"
    assert card["severity"] == "grave"
    assert card["severity_reason"] == "Alerte du CERT-FR, qui signale un danger immédiat."
    assert card["audience"] == "entreprises"
    assert card["victim"] == {"label": "Utilisateurs des produits cités", "status": "confirme"}
    assert card["method"] == "Faille signalée par le CERT-FR"
    assert card["loot"] is None
    assert card["am_i_affected"] == "Oui, si vous utilisez un produit cité dans l'alerte."
    assert card["action"] == "Suivez les recommandations de l'alerte du CERT-FR."
    assert card["first_seen"] == "2026-11-18"
    assert card["summary"] == [
        "Le CERT-FR a publié le 18 novembre 2026 l'alerte CERTFR-2026-ALE-017 : "
        "Multiples vulnérabilités dans F5 NGINX."
    ]
    assert card["sources"] == [{
        "name": "CERT-FR",
        "title": "Alerte CERTFR-2026-ALE-017",
        "url": "https://www.cert.cyber.gouv.fr/alerte/CERTFR-2026-ALE-017/",
        "official": True,
    }]


def test_certfr_titles_lose_the_update_mark_and_the_date():
    assert cards.clean_alert_title("[MàJ] Vulnérabilité dans OpenSSH (05 novembre 2026)") == "Vulnérabilité dans OpenSSH"
    assert cards.clean_alert_title("[Màj] Multiples vulnérabilités dans PHP (21 octobre 2026)") == "Multiples vulnérabilités dans PHP"
    assert cards.clean_alert_title("Vulnérabilité dans Exemple (1er décembre 2026)") == "Vulnérabilité dans Exemple"


def test_certfr_long_titles_wait_for_phase_two():
    assert cards.certfr_card(ALERTS["CERTFR-2026-ALE-012"]) is None


def test_certfr_consumer_products():
    alert = ALERTS["CERTFR-2026-ALE-017"]
    chrome = alert.model_copy(update={"title": "Vulnérabilité dans Google Chrome (19 novembre 2026)"})
    assert cards.certfr_card(chrome)["audience"] == "les_deux"
    whatsapp = alert.model_copy(update={"title": "Vulnérabilité dans WhatsApp (19 novembre 2026)"})
    assert cards.certfr_card(whatsapp)["audience"] == "les_deux"
    cisco = alert.model_copy(update={"title": "Multiples vulnérabilités dans Cisco IOS XE (19 novembre 2026)"})
    assert cards.certfr_card(cisco)["audience"] == "entreprises"
    for title in ("Vulnérabilité dans les box Freebox", "Vulnérabilité dans les routeurs TP-Link", "Vulnérabilité dans QNAP QTS"):
        assert cards.certfr_card(alert.model_copy(update={"title": title}))["audience"] == "les_deux", title


def test_certfr_cards_never_say_exploited():
    """An alert may report a flaw nobody has exploited yet (ALE-017 only mentions a public proof of
    concept): the card must not say otherwise."""
    for alert in ALERTS.values():
        card = cards.certfr_card(alert.model_copy(update={"title": "Vulnérabilité dans Exemple"}))
        texts = [card["title"], card["severity_reason"], card["method"] or "", card["am_i_affected"],
                 card["action"], *card["summary"], *(event["label"] for event in card["timeline"])]
        assert not [text for text in texts if "exploit" in text.lower()]
        assert card["exploited"] is False


def test_only_a_source_that_says_so_makes_a_flaw_exploited():
    assert all(cards.kev_card(entry)["exploited"] for entry in ENTRIES.values())
    assert cards.claim_card(CLAIMS["Exemple Logistique SAS"])["exploited"] is False


def test_certfr_alert_without_cve_has_no_method():
    alert = ALERTS["CERTFR-2026-ALE-017"].model_copy(update={"cves": []})
    assert cards.certfr_card(alert)["method"] is None


def test_an_alert_citing_a_cisa_flaw_joins_its_card():
    entry = KevEntry(cve="CVE-2099-1234", vendor="Exemple", product="Passerelle", date_added=date(2026, 11, 17))
    alert = CertfrAlert(
        number="CERTFR-2099-ALE-001",
        title="Vulnérabilité dans Exemple Passerelle (18 novembre 2026)",
        url="https://www.cert.cyber.gouv.fr/alerte/CERTFR-2099-ALE-001/",
        published=datetime(2026, 11, 18, tzinfo=timezone.utc),
        cves=["CVE-2099-1234"],
    )
    built, held = cards.build([entry], [alert], [])
    assert len(built) == 1 and not held
    card = built[0]
    assert [source["name"] for source in card["sources"]] == ["CISA", "NVD", "CERT-FR"]
    assert {"date": "2026-11-18", "label": "Alerte CERTFR-2099-ALE-001 du CERT-FR"} in card["timeline"]
    assert card["severity"] == "grave"
    assert card["severity_reason"] == severity.CERTFR_ALERT[1]
    assert card["exploited"] is True  # the CISA confirms it, whatever the alert says


# ransomware.live


def test_claim_card():
    card = cards.claim_card(CLAIMS["Exemple Logistique SAS"])
    assert card["title"] == "Attaque revendiquée contre Exemple Logistique SAS"
    assert card["severity"] == "significative"
    assert card["severity_reason"] == "Revendication non confirmée : niveau limité à « Significative »."
    assert card["audience"] == "entreprises"
    assert card["reliability"] == "confirme"
    assert card["attacker"] == {"name": "Groupe Ombrefictive", "country": None, "status": "revendique", "source": None}
    assert card["victim"] == {"label": "Exemple Logistique SAS", "status": "revendique"}
    assert card["method"] == "Inconnue à ce stade"
    assert card["loot"] == "Données volées, selon les pirates"
    assert card["am_i_affected"] == "Peut-être, si vous êtes client ou salarié de cette organisation."
    assert card["action"] == "Méfiez-vous des messages qui citent cette organisation."
    assert card["first_seen"] == "2026-11-18T10:41:27Z"
    assert card["sources"] == [{
        "name": "ransomware.live",
        "title": "Revendication du groupe Ombrefictive",
        "url": "https://www.ransomware.live/id/RXhlbXBsZSBMb2dpc3RpcXVlIFNBU0BvbWJyZWZpY3RpdmU=",
        "official": False,
    }]
    assert card["id"].startswith("rl-") and "exemple" not in card["id"].lower()


def test_claim_title_falls_back_on_the_group():
    card = cards.claim_card(CLAIMS["Groupement Interprofessionnel Des Producteurs Fictifs De La Vallee Imaginaire"])
    assert card["title"] == "Attaque revendiquée par le groupe Verrou-imaginaire"


def test_names_that_look_like_a_person():
    for name in ("Dr Exemple Fictif", "Jean Fictif", "Cabinet de Maître Fictif", "Me Fictif", "JEAN-PIERRE FICTIF"):
        assert cards.looks_like_person(name), name
    for name in ("Exemple Logistique SAS", "Mairie de Fictiville", "Jean Fictif Transports",
                 "exemple-logistique.example", "Fictiville", "Martin"):
        assert not cards.looks_like_person(name), name


def test_build_holds_back_people_and_long_alerts():
    alerts = [ALERTS["CERTFR-2026-ALE-012"], ALERTS["CERTFR-2026-ALE-017"]]
    built, held = cards.build([], alerts, list(CLAIMS.values()))
    titles = [card["title"] for card in built]
    assert "Multiples vulnérabilités dans F5 NGINX" in titles
    assert not [title for title in titles if "Fictif" in title and ("Dr " in title or "Jean" in title)]
    reasons = [reason for reason, _ in held]
    assert reasons.count("nom qui ressemble à celui d'une personne") == 2
    assert reasons.count("titre d'alerte de plus de 10 mots, en attente de la phase 2") == 1


def test_the_safety_net_runs_last():
    card = cards.claim_card(CLAIMS["Exemple Logistique SAS"])
    card["severity"] = "critique"
    capped = severity.cap_claim(card)
    assert capped["severity"] == "significative"
    assert capped["severity_reason"] == severity.CLAIM[1]

"""Phase 1 cards (B6), in French and in English: each template and its generic variants, the
CERT-FR rules and title translation, the claims, the general public deduced from the product, the
names held back and the safety net."""

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


def both(fr: str, en: str) -> dict:
    return {"fr": fr, "en": en}


def texts_of(card: dict) -> list[dict]:
    """Every text of a card, each one a {fr, en} pair."""
    found = [card["severity_reason"], card["title"], card["victim"]["label"]]
    found += [card[field] for field in ("method", "loot", "am_i_affected", "action")]
    found += card["summary"] + card["protection_steps"] + [event["label"] for event in card["timeline"]]
    found += [source["title"] for source in card["sources"]]
    if card["attacker"]:
        found += [card["attacker"]["name"], card["attacker"]["country"]]
    return [text for text in found if text is not None]


# CISA


def test_kev_widespread_software_is_grave():
    card = card_for("CVE-2024-10441")  # Synology DiskStation Manager (DSM)
    assert card["severity"] == "grave"
    assert card["severity_reason"] == both("Faille déjà exploitée dans un logiciel répandu.", "Flaw already exploited in widespread software.")
    assert card["title"] == both("Faille exploitée dans Synology DSM", "Exploited flaw in Synology DSM")
    assert card["victim"] == {"label": both("Utilisateurs de Synology DSM", "Synology DSM users"), "status": "confirme"}
    assert card["am_i_affected"] == both(
        "Oui, si vous utilisez Synology DSM sans la dernière mise à jour.",
        "Yes, if you use Synology DSM without the latest update.",
    )
    assert card["action"] == both(
        "Installez la mise à jour de sécurité de Synology sans attendre.",
        "Install the Synology security update without delay.",
    )
    assert card["audience"] == "les_deux"  # a NAS, found at home too
    assert card["first_seen"] == "2026-11-18"
    assert card["summary"] == [both(
        "Encodage de sortie incorrect dans Synology DSM : un attaquant à distance peut exécuter du code. "
        "La CISA l'a ajoutée à sa liste des failles exploitées le 18 novembre 2026.",
        "Improper output encoding in Synology DSM: a remote attacker can run code. "
        "CISA added it to its list of exploited flaws on 18 November 2026.",
    )]
    assert card["technical"]["software"] == ["Synology DiskStation Manager (DSM)"]
    assert card["kind"] == "faille"


def test_kev_less_common_software_is_significant():
    card = card_for("CVE-2026-40217")  # BerriAI LiteLLM
    assert card["severity"] == "significative"
    assert card["severity_reason"] == both("Faille déjà exploitée, dans un logiciel peu répandu.", "Flaw already exploited, in less common software.")
    assert card["title"] == both("Faille exploitée dans BerriAI LiteLLM", "Exploited flaw in BerriAI LiteLLM")
    assert card["victim"]["label"] == both("Utilisateurs de BerriAI LiteLLM", "BerriAI LiteLLM users")
    assert card["am_i_affected"] == both(
        "Oui, si vous utilisez BerriAI LiteLLM sans la dernière mise à jour.",
        "Yes, if you use BerriAI LiteLLM without the latest update.",
    )
    assert card["method"] == both("Canal alternatif non protégé", "Unprotected alternate channel")
    assert card["loot"] == both("Exécution de code à distance", "Remote code execution")


def test_kev_method_is_the_type_of_flaw():
    """From the name the CISA gives the flaw, else from its CWE numbers; generic when unknown."""
    assert card_for("CVE-2026-90817")["method"] == both("Injection de code", "Code injection")  # name, not CWE-73
    assert card_for("CVE-2026-59310")["method"] == both("Traversée de répertoires", "Path traversal")
    assert card_for("CVE-2026-125350")["method"] == both("Utilisation de mémoire libérée", "Use after free")
    assert card_for("CVE-2008-4128")["method"] == both("Falsification de requête intersite (CSRF)", "Cross-site request forgery (CSRF)")
    # "Remote Code Execution Vulnerability", without CWE: the type is not known.
    assert card_for("CVE-2010-3765")["method"] == both("Faille déjà exploitée par des attaquants", "Flaw already exploited by attackers")
    entry = KevEntry(cve="CVE-2099-0004", vendor="Exemple", product="Passerelle", name="Exemple Passerelle Vulnerability",
                     cwes=["CWE-89"], date_added=date(2026, 11, 18))
    assert cards.kev_card(entry)["method"] == both("Injection SQL", "SQL injection")  # from the CWE


def test_kev_impact_comes_from_the_words_of_the_cisa():
    assert card_for("CVE-2026-90817")["loot"] == both("Exécution de code", "Code execution")  # no "remote" in the text
    assert card_for("CVE-2008-4128")["loot"] == both("Exécution de commandes à distance", "Remote command execution")
    assert card_for("CVE-2026-123039")["loot"] == both("Élévation de privilèges", "Privilege escalation")  # "executed as root"
    assert card_for("CVE-2026-96951")["loot"] == both("Contournement d'une protection", "Protection bypass")
    entry = KevEntry(cve="CVE-2099-0005", vendor="Exemple", product="Passerelle", description="Exemple Passerelle contains a flaw.",
                     date_added=date(2026, 11, 18))
    assert cards.kev_card(entry)["loot"] is None  # nothing in the table: "Non communiqué" on the site


def test_kev_who_can_exploit_the_flaw_is_read_in_the_sentence_of_the_impact():
    summary = card_for("CVE-2026-123039")["summary"][0]  # Check Point: the second sentence names the user
    assert summary["fr"].startswith(
        "Permissions mal attribuées dans des produits Check Point : un utilisateur local connecté peut obtenir des droits plus élevés."
    )
    assert summary["en"].startswith(
        "Incorrect permission assignment in Check Point products: a logged-in local user can gain higher privileges."
    )
    axis = card_for("CVE-2026-90436")["summary"][0]
    assert axis["fr"].startswith("Réflexion non sûre dans Apache Axis : un attaquant à distance, sans compte, peut exécuter du code.")
    assert axis["en"].startswith("Unsafe reflection in Apache Axis: a remote attacker without an account can run code.")
    windows = card_for("CVE-2026-96951")["summary"][0]
    assert windows["en"].startswith("Command injection in Microsoft Windows: an unauthorized remote attacker can get around a protection.")
    # "as the service user" names no one who exploits the flaw: the actor follows "allows", or
    # is the subject of the sentence.
    puppet = card_for("CVE-2026-115731")["summary"][0]
    assert puppet["fr"].startswith("Désérialisation de données non fiables dans Perforce Puppet Enterprise : un attaquant peut exécuter du code.")


def test_kev_summaries_differ_from_card_to_card():
    """Each summary says what the flaw is and allows; the CISA is introduced in "Méthode et sources"."""
    built = [cards.kev_card(entry) for entry in ENTRIES.values()]
    openings = [card["summary"][0]["fr"].split(". ")[0] for card in built]
    assert len(set(openings)) == len(openings)
    assert not any("agence américaine" in card["summary"][0]["fr"] or "US cybersecurity agency" in card["summary"][0]["en"] for card in built)


def test_kev_uses_the_short_name_in_brackets():
    card = card_for("CVE-2026-90817")  # Vanderbilt University, Research Electronic Data Capture (REDCap)
    assert card["title"] == both("Faille exploitée dans REDCap", "Exploited flaw in REDCap")
    assert card["victim"]["label"] == both("Utilisateurs de REDCap", "REDCap users")
    assert card["am_i_affected"] == both(
        "Oui, si vous utilisez REDCap sans la dernière mise à jour.",
        "Yes, if you use REDCap without the latest update.",
    )
    assert card["summary"][0]["fr"].startswith("Injection de code dans REDCap : un attaquant sans compte peut exécuter du code.")
    assert card["summary"][0]["en"].startswith("Code injection in REDCap: an attacker without an account can run code.")
    assert card["technical"]["software"] == ["Vanderbilt University Research Electronic Data Capture (REDCap)"]  # full name


def test_both_languages_always_take_the_same_variant():
    # The French action naming Vanderbilt University is too long; the English one would fit, but
    # both use the generic sentence so that they say the same thing.
    card = card_for("CVE-2026-90817")
    assert card["action"] == both(
        "Installez la dernière mise à jour de sécurité sans attendre.",
        "Install the latest security update without delay.",
    )


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
    assert card["victim"]["label"] == both("Utilisateurs de ce logiciel", "Users of this software")
    assert card["am_i_affected"] == both(
        "Oui, si vous utilisez ce logiciel sans la dernière mise à jour.",
        "Yes, if you use this software without the latest update.",
    )
    assert card["action"] == both(
        "Installez la dernière mise à jour de sécurité sans attendre.",
        "Install the latest security update without delay.",
    )
    assert all(len(title.split()) <= 10 for title in card["title"].values())


def test_kev_title_falls_back_on_the_vendor_then_on_a_generic_title():
    product = "Un Produit Au Nom Vraiment Beaucoup Trop Long Pour Un Titre"
    entry = KevEntry(cve="CVE-2099-0001", vendor="Exemple", product=product, date_added=date(2026, 11, 18))
    assert cards.kev_card(entry)["title"] == both("Faille exploitée dans un logiciel d'Exemple", "Exploited flaw in Exemple software")
    entry = entry.model_copy(update={"vendor": "Un Éditeur Au Nom Vraiment Beaucoup Trop Long"})
    assert cards.kev_card(entry)["title"] == both("Faille exploitée dans un logiciel", "Exploited flaw in software")


def test_kev_elision_and_articles():
    card = card_for("CVE-2026-90436")  # Apache Axis
    assert card["victim"]["label"] == both("Utilisateurs d'Apache Axis", "Apache Axis users")
    assert card["action"] == both(
        "Installez la mise à jour de sécurité d'Apache sans attendre.",
        "Install the Apache security update without delay.",
    )
    assert card["severity"] == "significative"  # not one of Apache's widespread programs
    apple = card_for("CVE-2024-27834")
    assert apple["am_i_affected"]["en"] == "Yes, if you use an Apple product without the latest update."


def test_kev_widespread_programs_and_ransomware_use():
    card = card_for("CVE-2021-45046")  # Apache Log4j2, used by ransomware
    assert card["severity"] == "grave"
    assert card["summary"][0]["fr"].endswith("Elle sert déjà dans des attaques par rançongiciel, selon la CISA.")
    assert card["summary"][0]["en"].endswith("According to CISA, it is already used in ransomware attacks.")
    assert card["attacker"] == {
        "name": both("Utilisée par des rançongiciels, selon la CISA", "Used by ransomware, according to CISA"),
        "country": None,
        "status": "confirme",
        "source": "CISA",
    }
    assert card_for("CVE-2026-40217")["attacker"]["status"] == "inconnu"  # "Unknown" ransomware use: origin unknown
    assert card_for("CVE-2026-59310")["severity"] == "grave"  # VMware, filed under Broadcom
    assert card_for("CVE-2026-123039")["severity"] == "grave"  # Check Point


def test_kev_summary_timeline_sources():
    card = card_for("CVE-2026-40217")
    assert card["summary"] == [both(
        "Canal alternatif non protégé dans BerriAI LiteLLM : un attaquant à distance peut exécuter du code. "
        "La CISA l'a ajoutée à sa liste des failles exploitées le 18 novembre 2026.",
        "Unprotected alternate channel in BerriAI LiteLLM: a remote attacker can run code. "
        "CISA added it to its list of exploited flaws on 18 November 2026.",
    )]
    assert card["timeline"] == [
        {"date": "2026-11-18", "label": both("Ajout à la liste des failles exploitées de la CISA", "Added to the CISA list of exploited flaws")},
        {"date": "2026-12-02", "label": both("Date limite de correction pour les administrations américaines", "Deadline for US federal agencies to fix it")},
    ]
    assert card["sources"] == [
        {
            "name": "CISA",
            "title": both("Catalogue des failles exploitées : CVE-2026-40217", "Known Exploited Vulnerabilities catalog: CVE-2026-40217"),
            "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext=CVE-2026-40217",
            "official": True,
        },
        {
            "name": "NVD",
            "title": both("Fiche CVE-2026-40217", "CVE-2026-40217 record"),
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2026-40217",
            "official": True,
        },
    ]
    assert card["attacker"] == {"name": None, "country": None, "status": "inconnu", "source": None}
    assert card["technical"] == {"cves": ["CVE-2026-40217"], "software": ["BerriAI LiteLLM"], "techniques": []}


def test_kev_multiple_products_use_the_vendor():
    card = card_for("CVE-2024-27834")  # Apple, "Multiple Products"
    assert card["title"] == both("Faille exploitée dans des produits Apple", "Exploited flaw in Apple products")
    assert card["victim"]["label"] == both("Utilisateurs de produits Apple", "Users of Apple products")
    assert card["am_i_affected"]["fr"] == "Oui, si vous utilisez un produit Apple sans la dernière mise à jour."


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
    assert card["title"] == both("Multiples vulnérabilités dans F5 NGINX", "Multiple vulnerabilities in F5 NGINX")
    assert card["severity"] == "grave"
    assert card["severity_reason"] == both(
        "Alerte du CERT-FR, qui signale un danger immédiat.",
        "CERT-FR alert, which warns of an immediate danger.",
    )
    assert card["audience"] == "entreprises"
    assert card["victim"] == {"label": both("Utilisateurs des produits cités", "Users of the products named"), "status": "confirme"}
    assert card["method"] == both("Faille signalée par le CERT-FR", "Flaw reported by CERT-FR")
    assert card["loot"] is None
    assert card["am_i_affected"] == both(
        "Oui, si vous utilisez un produit cité dans l'alerte.",
        "Yes, if you use a product named in the alert.",
    )
    assert card["action"] == both(
        "Suivez les recommandations de l'alerte du CERT-FR.",
        "Follow the recommendations of the CERT-FR alert.",
    )
    assert card["first_seen"] == "2026-11-18"
    # Without its page (robots.txt, or a page that cannot be read), the card says what the feed says.
    assert card["summary"] == [both(
        "Alerte du CERT-FR du 18 novembre 2026 : Multiples vulnérabilités dans F5 NGINX.",
        "CERT-FR alert of 18 November 2026: Multiple vulnerabilities in F5 NGINX.",
    )]
    assert card["kind"] == "faille"
    assert card["sources"] == [{
        "name": "CERT-FR",
        "title": both("Alerte CERTFR-2026-ALE-017", "Alert CERTFR-2026-ALE-017"),
        "url": "https://www.cert.cyber.gouv.fr/alerte/CERTFR-2026-ALE-017/",
        "official": True,
    }]
    assert card["untranslated"] == []


def test_certfr_targets_and_impact_come_from_the_alert_page():
    cves, systems, risks = certfr.page_details(sample("certfr-page.html").decode("utf-8"))
    assert systems[0] == "NGINX Open Source versions 1.31.x antérieures à 1.31.9" and len(systems) == 4
    assert risks == ["Exécution de code arbitraire à distance"]
    alert = ALERTS["CERTFR-2026-ALE-017"].model_copy(update={"systems": systems, "risks": risks})
    card = cards.certfr_card(alert)
    assert card["victim"]["label"] == both("Utilisateurs de produits NGINX", "Users of NGINX products")
    assert card["loot"] == both("Exécution de code arbitraire à distance", "Remote arbitrary code execution")
    assert card["summary"] == [both(
        "Alerte du CERT-FR du 18 novembre 2026 : exécution de code arbitraire à distance dans NGINX Open Source et NGINX Plus.",
        "CERT-FR alert of 18 November 2026: remote arbitrary code execution in NGINX Open Source and NGINX Plus.",
    )]


def test_certfr_targets_fit_or_fall_back():
    def label(systems):
        alert = ALERTS["CERTFR-2026-ALE-017"].model_copy(update={"systems": systems})
        return cards.certfr_card(alert)["victim"]["label"]

    assert label(["FortiOS 7.4.x antérieures à 7.4.5"]) == both("Utilisateurs de FortiOS", "FortiOS users")
    assert label(["Ivanti EPMM versions 12.x antérieures à 12.5", "Ivanti Neurons 1.x"]) == both(
        "Utilisateurs d'Ivanti EPMM et Ivanti Neurons", "Ivanti EPMM and Ivanti Neurons users"
    )
    # Two names too long together: the vendor they share.
    assert label(["Exemple Passerelle versions antérieures à 2.1", "Exemple Console 3.x"]) == both(
        "Utilisateurs de produits Exemple", "Users of Exemple products"
    )
    assert label(["Oracle Java SE version 21", "Oracle GraalVM for JDK version 17", "Oracle GraalVM Enterprise Edition version 21"]) == both(
        "Utilisateurs de produits Oracle", "Users of Oracle products"
    )
    assert label(["Produit Un 1.2", "Autre Produit 3.4", "Encore Un 5.6"]) == both(
        "Utilisateurs des produits cités", "Users of the products named"
    )


def test_certfr_risks_are_translated_by_a_table_and_ordered():
    risks = ["Déni de service à distance", "Atteinte à la confidentialité des données", "Exécution de code arbitraire à distance",
             "Non spécifié par l'éditeur"]
    assert cards.flaws.known_risks(risks) == [
        ("Exécution de code arbitraire à distance", "Remote arbitrary code execution"),
        ("Atteinte à la confidentialité des données", "Breach of data confidentiality"),
        ("Déni de service à distance", "Remote denial of service"),
    ]
    alert = ALERTS["CERTFR-2026-ALE-017"].model_copy(update={"risks": ["Non spécifié par l'éditeur"]})
    assert cards.certfr_card(alert)["loot"] is None  # unknown to the table: "Non communiqué"


def test_certfr_titles_in_the_usual_forms_are_translated():
    translate = cards.translate_alert_title
    assert translate("Vulnérabilité dans Oracle Java SE") == "Vulnerability in Oracle Java SE"
    assert translate("Multiples vulnérabilités dans F5 NGINX") == "Multiple vulnerabilities in F5 NGINX"
    assert translate("Vulnérabilités affectant OpenPrinting CUPS") == "Vulnerabilities affecting OpenPrinting CUPS"
    assert translate("Vulnérabilité dans les produits Ivanti") == "Vulnerability in Ivanti products"
    assert translate("Vulnérabilité critique dans Exemple Gateway") == "Critical vulnerability in Exemple Gateway"


def test_certfr_titles_that_would_need_inventing_stay_in_french_and_are_flagged():
    translate = cards.translate_alert_title
    assert translate("Incident de sécurité ciblant les contrôleurs à distance") is None
    assert translate("Vulnérabilité dans le noyau Linux") is None
    assert translate("Multiples vulnérabilités sur l'interface d'administration des équipements Exemple") is None
    alert = ALERTS["CERTFR-2026-ALE-017"].model_copy(update={"title": "Campagne d'hameçonnage visant les collectivités"})
    card = cards.certfr_card(alert)
    assert card["title"] == both("Campagne d'hameçonnage visant les collectivités", "Campagne d'hameçonnage visant les collectivités")
    assert card["untranslated"] == ["title"]


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
    concept): the card must not say otherwise, in either language."""
    for alert in ALERTS.values():
        card = cards.certfr_card(alert.model_copy(update={"title": "Vulnérabilité dans Exemple"}))
        written = [value for pair in texts_of(card) for value in pair.values()]
        assert not [value for value in written if "exploit" in value.lower()]
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
    assert {"date": "2026-11-18", "label": both("Alerte CERTFR-2099-ALE-001 du CERT-FR", "CERT-FR alert CERTFR-2099-ALE-001")} in card["timeline"]
    assert card["severity"] == "grave"
    assert card["severity_reason"] == severity.CERTFR_ALERT[1]
    assert card["exploited"] is True  # the CISA confirms it, whatever the alert says


# ransomware.live


def test_claim_card():
    card = cards.claim_card(CLAIMS["Exemple Logistique SAS"])
    assert card["title"] == both("Attaque revendiquée contre Exemple Logistique SAS", "Attack claimed against Exemple Logistique SAS")
    assert card["severity"] == "significative"
    assert card["severity_reason"] == both(
        "Revendication non confirmée : niveau limité à « Significative ».",
        "Unconfirmed claim: level capped at “Significant”.",
    )
    assert card["audience"] == "entreprises"
    assert card["reliability"] == "confirme"
    assert card["attacker"] == {"name": both("Groupe Ombrefictive", "Ombrefictive group"), "country": None, "status": "revendique", "source": None}
    assert card["victim"] == {"label": both("Exemple Logistique SAS", "Exemple Logistique SAS"), "status": "revendique"}
    assert card["method"] == both("Inconnue à ce stade", "Unknown at this stage")
    assert card["loot"] == both("Données volées, selon les pirates", "Data stolen, according to the attackers")
    assert card["am_i_affected"] == both(
        "Peut-être, si vous êtes client ou salarié de cette organisation.",
        "Maybe, if you are a customer or an employee of this organisation.",
    )
    assert card["action"] == both(
        "Méfiez-vous des messages qui citent cette organisation.",
        "Be wary of messages that mention this organisation.",
    )
    assert card["summary"][0]["en"] == (
        "The Ombrefictive group claims to have attacked Exemple Logistique SAS. The claim was recorded "
        "by ransomware.live on 18 November 2026. It is not confirmed at this stage."
    )
    assert card["first_seen"] == "2026-11-18T10:41:27Z"
    assert card["sources"] == [{
        "name": "ransomware.live",
        "title": both("Revendication du groupe Ombrefictive", "Claim by the Ombrefictive group"),
        "url": "https://www.ransomware.live/id/RXhlbXBsZSBMb2dpc3RpcXVlIFNBU0BvbWJyZWZpY3RpdmU=",
        "official": False,
    }]
    assert card["id"].startswith("rl-") and "exemple" not in card["id"].lower()


def test_claim_title_falls_back_on_the_group():
    card = cards.claim_card(CLAIMS["Groupement Interprofessionnel Des Producteurs Fictifs De La Vallee Imaginaire"])
    assert card["title"] == both("Attaque revendiquée par le groupe Verrou-imaginaire", "Attack claimed by the Verrou-imaginaire group")


def test_names_that_look_like_a_person():
    for name in ("Dr Exemple Fictif", "Jean Fictif", "Cabinet de Maître Fictif", "Me Fictif", "JEAN-PIERRE FICTIF"):
        assert cards.looks_like_person(name), name
    for name in ("Exemple Logistique SAS", "Mairie de Fictiville", "Jean Fictif Transports",
                 "exemple-logistique.example", "Fictiville", "Martin"):
        assert not cards.looks_like_person(name), name


def test_build_holds_back_people_and_long_alerts():
    alerts = [ALERTS["CERTFR-2026-ALE-012"], ALERTS["CERTFR-2026-ALE-017"]]
    built, held = cards.build([], alerts, list(CLAIMS.values()))
    titles = [card["title"]["fr"] for card in built]
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


# Both languages


def test_every_text_of_every_card_exists_in_both_languages():
    built, _ = cards.build(list(ENTRIES.values()), list(ALERTS.values()), list(CLAIMS.values()))
    assert built
    for card in built:
        for pair in texts_of(card):
            assert set(pair) == {"fr", "en"}, card["id"]
            assert all(isinstance(value, str) and value.strip() for value in pair.values()), card["id"]


def test_the_collector_writes_no_typography_of_either_language():
    """The site adds French typography to French texts only: the collector writes plain spaces."""
    built, _ = cards.build(list(ENTRIES.values()), list(ALERTS.values()), list(CLAIMS.values()))
    for card in built:
        for pair in texts_of(card):
            for value in pair.values():
                assert " " not in value and " " not in value
            if not card.get("untranslated"):
                assert " :" not in pair["en"] and " ;" not in pair["en"], pair["en"]

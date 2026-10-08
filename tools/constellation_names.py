"""Finder names keyed by stable IAU identity, independent of figure spelling.

English uses the project's customary English constellation names. Greek
genitives are explicit inflections, not Latin genitives or automatic suffixes.
Greek nominative reference: https://www.astrovox.gr/articles/βασικές-γνώσεις/οι-αστερισμοί-r4/
"""
from compute_constellation_observance_2026 import CONSTELLATIONS

ENGLISH = {abbr: name for name, abbr in CONSTELLATIONS}
ENGLISH.update(Cap="Capricorn", Del="Dolphin")

GREEK_GENITIVE = {
    "And": "Ανδρομέδας", "Ant": "Αντλίας", "Aps": "Πτηνού",
    "Aqr": "Υδροχόου", "Aql": "Αετού", "Ara": "Βωμού",
    "Ari": "Κριού", "Aur": "Ηνιόχου", "Boo": "Βοώτη",
    "Cae": "Γλυφείου", "Cam": "Καμηλοπαρδάλεως", "Cnc": "Καρκίνου",
    "CVn": "Θηρευτικών Κυνών", "CMa": "Μεγάλου Κυνός", "CMi": "Μικρού Κυνός",
    "Cap": "Αιγόκερω", "Car": "Τρόπιδος", "Cas": "Κασσιόπης",
    "Cen": "Κενταύρου", "Cep": "Κηφέως", "Cet": "Κήτους",
    "Cha": "Χαμαιλέοντος", "Cir": "Διαβήτη", "Col": "Περιστεράς",
    "Com": "Κόμης Βερενίκης", "CrA": "Νοτίου Στεφάνου", "CrB": "Βορείου Στεφάνου",
    "Crv": "Κόρακος", "Crt": "Κρατήρος", "Cru": "Νοτίου Σταυρού",
    "Cyg": "Κύκνου", "Del": "Δελφινιού", "Dor": "Δοράδος",
    "Dra": "Δράκοντος", "Equ": "Ιππαρίου", "Eri": "Ηριδανού",
    "For": "Καμίνου", "Gem": "Διδύμων", "Gru": "Γερανού",
    "Her": "Ηρακλή", "Hor": "Ωρολογίου", "Hya": "Ύδρας",
    "Hyi": "Ύδρου", "Ind": "Ινδού", "Lac": "Σαύρας",
    "Leo": "Λέοντος", "LMi": "Μικρού Λέοντος", "Lep": "Λαγωού",
    "Lib": "Ζυγού", "Lup": "Λύκου", "Lyn": "Λυγκός",
    "Lyr": "Λύρας", "Men": "Τραπέζης", "Mic": "Μικροσκοπίου",
    "Mon": "Μονόκερω", "Mus": "Μυίας", "Nor": "Γνώμονος",
    "Oct": "Οκτάντος", "Oph": "Οφιούχου", "Ori": "Ωρίωνος",
    "Pav": "Ταώ", "Peg": "Πηγάσου", "Per": "Περσέως",
    "Phe": "Φοίνικος", "Pic": "Οκρίβαντος", "Psc": "Ιχθύων",
    "PsA": "Νοτίου Ιχθύος", "Pup": "Πρύμνης", "Pyx": "Πυξίδος",
    "Ret": "Δικτύου", "Sge": "Βέλους", "Sgr": "Τοξότη",
    "Sco": "Σκορπιού", "Scl": "Γλύπτη", "Sct": "Ασπίδος",
    "Ser": "Όφεως", "Sex": "Εξάντος", "Tau": "Ταύρου",
    "Tel": "Τηλεσκοπίου", "Tri": "Τριγώνου", "TrA": "Νοτίου Τριγώνου",
    "Tuc": "Τουκάνας", "UMa": "Μεγάλης Άρκτου", "UMi": "Μικρής Άρκτου",
    "Vel": "Ιστίων", "Vir": "Παρθένου", "Vol": "Ιπταμένου Ιχθύος",
    "Vul": "Αλώπεκος",
}

_ABBREVIATIONS = {name: abbr for name, abbr in CONSTELLATIONS}
_ABBREVIATIONS.update({name: abbr for abbr, name in ENGLISH.items()})
_ABBREVIATIONS.update({abbr: abbr for abbr in ENGLISH})
_ABBREVIATIONS["Bootes"] = "Boo"


def naming_identity(name, abbreviation=""):
    return abbreviation if abbreviation in ENGLISH else _ABBREVIATIONS.get(name)


def constellation_names(name, abbreviation=""):
    abbr = naming_identity(name, abbreviation)
    if abbr is None:
        raise ValueError(f"Unknown constellation identity: {name!r}, {abbreviation!r}")
    return abbr, {"greek": ENGLISH[abbr], "latin": ENGLISH[abbr],
                  "mixed": ENGLISH[abbr]}


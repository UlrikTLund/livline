#!/usr/bin/env python3
"""
Livline-PC — Telegram Bot-terminal (Model A: én bot pr. maskine)
VERSION 4.92

Versionen står her i linje 4, så den kan ses uden at rulle. Den SKAL
stemme med VERSION-konstanten længere nede — en prøve håndhæver det, og
install.sh afviser filen, hvis de to er uenige.

Ændringsloggen er flyttet til livline-aendringslog.md. Den fyldte 571
linjer her og var samtidig forældet: den sagde 4.35, mens maskinen kørte
4.51. En forældet forklaring er værre end ingen — den bliver troet.


Erstatter Telegram Desktop + xdotool/wmctrl-laget helt: appen ER terminalen.
Ingen X11-afhængighed — kører på Wayland (Ubuntu 24.04/26.04 standard).
Intet telefonnummer — botten autentificerer med en statisk token.

Tilstand — sættes med "mode" i config (faellestraad | enkelte):
    faellestraad      én samtale; alle godkendte ser alles beskeder
    enkelte           hver person sin egen samtale, op til fem på F-taster

Betjening — sættes med "betjening" i config (knapper | tastatur):
    1-9               faste svar (knapper i bunden, tekster fra "svar")
    Skriv + Enter     fri besked i skrivefeltet nederst
    Pil op/ned        scroller i beskederne; efter 5 min inaktivitet rulles
                      automatisk tilbage til nyeste besked
    F2 F4 F6 F8 F10   vælg familiemedlem (kun i "enkelte"-tilstand)

Den ENESTE kommando, familien bruger:
    /start               beder om adgang. Den fremmede får svar med det
                         samme, og administrator får en ⚠️ med et navn og
                         en godkend-knap. Uden den skete der INTET, når
                         nogen trykkede Start — og vejledningen bad dem om
                         netop det.

Administration hjemmefra (kun fra admin_chat_id, dvs. din egen Telegram):
    /status              maskinstatus: oppetid, disk, whitelist
    /tilfoej <id> <navn> tilføj familiemedlem til whitelist
    /fjern <id>          fjern fra whitelist
    /liste               vis whitelist (med F-taster)
    /opdater             hent og installér ny programversion fra update_url:
                         downloader, syntakstjekker FØR udskiftning, tager
                         backup (.bak), udskifter sig selv og genstarter via
                         run.sh. run.sh ruller tilbage til .bak ved crash-loop.
    /indstillinger       vis hvad maskinen FAKTISK bruger
    /skaerm              send et billede af brugerens skærm
    /hjaelp              vis kommandoer
Desuden: ÉN planlagt besked om dagen — ☀️ kl. 8 med oppetid, disk, batteri
og dage siden familien sidst skrev. Alarmer (ukendt person, rollback,
stavefejl i config) sendes straks og tæller ikke med i den ene.
(med chat_id klar til /tilfoej).

Afhængigheder (Ubuntu) — install.sh klarer det hele:
    sudo apt install python3-tk python3-pil python3-pil.imagetk \
                     python3-venv openssl
    Ingen afspiller og ingen lydpakker: Livline er skærm og tastatur.
    /opt/livline/venv/bin/pip install "python-telegram-bot>=22,<23"
    Biblioteket ligger i appens EGET miljø, ikke i systemets Python.
    Brug ALDRIG --break-system-packages: det bryder Ubuntus beskyttelse
    af systemets Python, og en senere systemopgradering kan så fjerne
    biblioteket fra stien, hvorefter appen ikke starter.

Konfiguration: /etc/livline/config.json  (ejer root:<kioskbruger>, mode 640)
{
    "token": "123456:ABC-DEF...",
    "admin_chat_id": 987654321,
    "machine_name": "Farmors Livline",
    "mode": "faellestraad",            // eller "enkelte"
    "media_dir": "/var/lib/livline/media",
    "whitelist_path": "/var/lib/livline/whitelist.json",   // historik.json
                                                           // lægges samme sted
    "update_url": "https://gist.githubusercontent.com/.../raw/livline_bot.py"
}

UDSEENDE: standarderne står i koden nedenfor (tema "kontrast", skrift 30,
sidemargen 60 osv.) og gælder derfor hele flåden — ret dem her og rul ud
med /opdater. Config-filen bruges KUN, hvis én bruger skal afvige:

    "skrift": 40,                     // svagtseende
    "tema": "gul",                    // sort på gul, "clear print"
    "farver": {"own": "#ff0000"},     // enkeltfarver: bg fg accent own day top btn
    "sidemargen": 60, "centreret": true, "blink": false,
    "betjening": "tastatur",          // knapper (standard) | tastatur
    "bobler": false,                  // flad liste i stedet for bobler
    "svar": ["Tak ❤️", "Ring til Mette 📞"],  // egne knaptekster (maks. 9)
    "taster": ["a", "f", "j", "æ"],   // genvejstaster i samme rækkefølge
                                      // (standard Q X T N O; æ ø å virker)
    "nat": [22, 8]                    // skærmen slukkes kl. 22, tændes kl. 8.
                                      // ÉT felt, ikke to — tallene betyder
                                      // kun noget i forhold til hinanden

BETJENING — vælg én efter brugerens evner (enten-eller):
    "knapper"   Faste svar. Enklest: intet at lære, intet at stave.
    "tastatur"  Skrivefelt: skriv frit og tryk Enter. Til dem, der kan og
                vil skrive selv. Knapperne vises ikke.
"skrift": punktstørrelse for beskedteksten (standard 30). Hæv til 36-44 for
svagtseende; navne, knapper og linjeafstand skaleres automatisk med.
"svar": tom liste [] = ingen faste svar overhovedet. Udeladt = standard.
"vis_knapper": false (standard) = ingen knaprad; teksterne står på tasterne.
               true = knapper på skærmen. Brug den på en TOUCH-skærm.

Tilstande:
    faellestraad  Alle godkendte ser alt: indgående beskeder genudsendes til
                  de øvrige familiemedlemmer, og brugerens svar går til alle.
    enkelte       Private 1:1-samtaler. Brugeren vælger modtager med
                  F-tasterne (F2 = første på whitelisten, F4 = anden, ...).

Whitelist: /var/lib/livline/whitelist.json — egen fil, så botten selv kan
opdatere den via /tilfoej og /fjern. Rækkefølgen bestemmer F-tasterne.
SIKKERHED: kun whitelistede afsendere når skærmen; alle andre afvises
stille, og administrator får besked.

Arkitektur: Tkinter i hovedtråden; python-telegram-bot (async) i baggrunds-
tråd med eget event loop. Indgående beskeder via thread-safe kø; udgående
via asyncio.run_coroutine_threadsafe. Botten venter selv på netværk ved
boot og genopretter ved udfald i stedet for at crashe (et crash-exit uden
netværk ville ellers udløse run.sh's rollback unødigt).
"""

import asyncio
import base64
import json
import logging
import os
import py_compile
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageTk
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

# Maskinen bruger altid /etc/livline/config.json. LIVLINE_CONFIG findes kun,
# så en prøveopsætning kan afvikles uden root — fx når en ny version skal
# testes på en almindelig PC, før den lægges i gisten.
CONFIG_PATH = Path(os.environ.get("LIVLINE_CONFIG", "/etc/livline/config.json"))
# Offentlig nøgle til at kontrollere, at en ny version kommer fra dig.
# FINDES DEN IKKE, er signering slået fra — se _tjek_signatur for hvorfor.
NOEGLE_STI = Path(os.environ.get("LIVLINE_NOEGLE",
                                 "/etc/livline/opdater.pub"))
VERSION = "4.92"
# Alle felter config.json må indeholde. Andet betragtes som en tastefejl
# og meldes til administrator ved opstart.
KENDTE_FELTER = {
    "token", "admin_chat_id", "machine_name", "mode", "media_dir",
    "whitelist_path", "update_url", "svar", "taster",
    "vis_knapper", "betjening", "autosend", "tema", "farver", "skrift", "fed",
    "sidemargen", "tekstbredde", "bobler", "blink", "stribe", "nat",
    "lysstyrke",
}
NET_TJEK_SEK = 30         # hvor ofte netvagten prøver at nå Telegram
NET_STILLE_SEK = 180      # hvor længe uden kontakt, før skærmen siger til.
                          # Tre minutter, fordi et kort udfald ikke skal
                          # sætte en advarsel op: en linje, der kommer og
                          # går hele dagen, holder man op med at læse.
REPLAY_IMAGES = 20        # hvor mange billeder der genskabes ved opstart
# Tk kender danske tegn under engelske navne (keysyms)
KEYSYM = {"æ": "ae", "ø": "oslash", "å": "aring",
          "Æ": "AE", "Ø": "Oslash", "Å": "Aring"}
HISTORY_MAX = 100         # antal beskeder der huskes på tværs af genstart
# Uden emoji: Tk på Linux kan ikke altid vise farve-emoji, og en tom
# firkant er værre end ingenting. Emoji kan sættes i "svar", hvis de
# viser sig korrekt på den konkrete skærm.
# STANDARDSVARENE ER PRØVET AF, IKKE gættet. De tre gamle ("Tak for
# beskeden", "Alt er godt", "Ring til mig") stod her, fordi de lød
# fornuftige. Disse fem er dem, maskine 01 endte med efter at have kørt i
# stuen: korte nok til at kunne læses på afstand, og med et modstykke til
# "alt er godt", så et svar kan bære en dårlig nyhed uden at man skal
# skrive den.
DEFAULT_REPLIES = ["Tak", "Nej tak", "Alt er godt",
                   "Ikke så godt", "Ring til mig"]
# Bogstaver frem for tal: de kan mærkes op på tasterne, og et bogstav, der
# hører til svaret, huskes lettere end en placering i en række. Valgt i
# praksis på maskine 01 — teksten sættes fysisk over tasterne, så der er
# plads til at læse dem.
DEFAULT_KEYS = ["Q", "X", "T", "N", "O"]
# Kvitteringen, som brugeren selv ser på skærmen, når hun trykker Enter.
# MÆRKET er det, der skiller en kvittering fra et rigtigt svar — også efter
# en genstart, hvor historikken kun har teksten at gå efter. Ændres teksten,
# skal mærket blive, ellers står gamle kvitteringer som "Du svarede".
#
# ORDLYDEN SKAL PASSE MED MÆRKATEN PÅ TASTEN. Det er den, brugeren kigger
# på, når hun trykker — står der noget andet på skærmen, er det to ting at
# forstå i stedet for én. "Beskeden er læst" er samtidig det samme ord som
# i hovedet ("Læst 14.05") og i det, familien får på telefonen.
KVIT_MAERKE = "👁"
KVIT_TEKST = "👁  Beskeden er læst"
IDLE_RESET_SEC = 300      # rul til nyeste besked efter 5 min inaktivitet
FELT_MIN = 1              # skrivefeltets højde i linjer, når det er tomt.
                          # Én linje, ikke to: to linjer plus luft og kant
                          # blev til en blok, der fyldte over 200 px og
                          # tog plads fra billederne. Feltet vokser
                          # alligevel med teksten, så pladsen er der,
                          # præcis når der er brug for den
FELT_MAX = 6              # ... og det højeste, det må vokse til
VINDUE_VAGT_TIDLIGE = 12  # antal 5-sekunders tjek af vinduet efter opstart
NAT_START = 22            # skærmen slukker kl. 22 …
NAT_SLUT = 8              # … og tænder igen kl. 8. Kan sættes pr. maskine
                          # med "nat": [22, 8] — ÉT felt, ikke to, fordi de
                          # to tal kun betyder noget i forhold til hinanden.
                          # Tallene her er standarden, når feltet mangler
NAT_TJEK_SEK = 30         # hvor tit maskinen ser på uret
NAT_VAEK_SEK = 120        # sekunder skærmen bliver tændt om natten, efter
                          # nogen har rørt en tast. Står hun op kl. 3 og vil
                          # se en besked, skal skærmen ikke slukke igen midt
                          # i læsningen — men den skal heller ikke stå tændt
                          # resten af natten, fordi en kat gik hen over den
RUL_ANDEL = 0.25          # hvor stor en del af SKÆRMEN ét tryk på pil op/ned
                          # ruller. Ikke en andel af hele samtalen — det var
                          # den gamle fejl: med mange beskeder blev hvert tryk
                          # til flere skærmfulde. En fjerdedel af det synlige
                          # er det samme, uanset hvor lang samtalen er, og
                          # lader altid noget af det læste blive stående
SEND_SVAR_FORSOEG = 60    # halve sekunder der ventes på svar fra Telegram,
                          # før en afsendelse regnes for mislykket (30 sek.)
SVAR_VINDUE_SEK = 10.0    # … og højst SVAR_MAKS_I_VINDUE svar i alt inden
SVAR_MAKS_I_VINDUE = 3    # for så mange sekunder. Spærringen ovenfor kunne
                          # omgås ved at ramme to taster skiftevis — Q, X,
                          # Q, X er aldrig "samme svar". Ingen sender fire
                          # forskellige svar på ti sekunder med vilje.
SVAR_PAUSE_SEK = 3.0      # mindste tid mellem to ENS svar.
                          # SET I DRIFT: holdes en tast nede, gentager
                          # tastaturet den tredive gange i sekundet — og
                          # familien fik tredive beskeder. En finger, der
                          # bliver liggende, en rystende hånd, en tast under
                          # en avis. Et ANDET svar går stadig igennem med
                          # det samme: trykker hun "Tak" og straks efter
                          # "Ring til mig", er det en beslutning, ikke et
                          # uheld — og den beslutning må aldrig bremses.
# ÉN REGEL FOR, HVORNÅR SKÆRMEN MÅ SKIFTE SAMTALE:
# der skal være kvitteret for det, der står nu.
#
# Erstattede en tidsgrænse på 25 sekunder. Tid er det forkerte mål — en
# besked er ikke læst, fordi den har stået længe nok. Med kvitteringskravet
# kan en besked aldrig blive skubbet væk af den næste, uanset hvor hurtigt
# den kommer, og uanset om brugeren er gået fra maskinen.
# Kvittering gives ved et tryk på en F-tast eller ved at sende en besked.
# SKRIFTEN FØLGER SKÆRMHØJDEN — ikke skærmens DPI-påstand.
#
# Tk regner skriftstørrelser i punkter og oversætter til pixels via DPI, som
# maskinen læser fra skærmens EDID. To ting går galt ad den vej:
#   1. EDID lyver. Målt i drift: en 14" skærm på 3072x1728 meldte sig som
#      813x457 mm — næsten tre gange for stor.
#   2. Skrivebordets egen skalering (200 % på skarpe skærme) lægges oveni,
#      uden at Tk ved det.
# Resultatet var, at "skrift": 28 gav 33 px på én maskine og 88 px på en
# anden. Et forsøg på at låse dpi til 96 gjorde det værre: på en skarp skærm
# ville teksten være blevet fysisk lillebitte.
#
# Løsningen er at måle, hvad der faktisk kom ud, og rette til, så teksten
# fylder den SAMME ANDEL af skærmhøjden på alle maskiner. Referencen er den
# maskine, konceptet blev afprøvet på: skrift 28 gav 44 px på en 768 px høj
# skærm. På 1728 px bliver samme andel til 99 px — og det er meningen.
SKRIFT_ANDEL = 44 / (768 * 28)   # px linjehøjde pr. skærmpixel pr. skriftpunkt
SKRIFT_PX = 0             # målt linjehøjde, vises i /indstillinger
# ÉN PLANLAGT BESKED OM DAGEN. Der var før fem: en startbesked plus et
# heartbeat hver sjette time. Med én maskine er det til at overskue, med
# ti er det halvtreds beskeder om dagen — og så holder man op med at læse
# dem. En alarm, ingen læser, er ikke en alarm.
#
# Nu sendes status én gang, kl. 8, sammen med morgenens livstegn. Alarmer
# (ukendt person, rollback, stavefejl i config) kommer stadig med det
# samme — det er kun det RUTINEMÆSSIGE, der er skåret ned.
FKEYS = ["F2", "F4", "F6", "F8", "F10"]

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
# SIKKERHED: httpx logger hele URL'en på INFO-niveau — og den indeholder
# bot-tokenen. Uden denne linje havner tokenen i klartekst i systemloggen
# (journalctl), hvor enhver med logadgang kan læse den.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.Updater").setLevel(logging.WARNING)
log = logging.getLogger("livline")

# ----------------------------------------------------------------------------
# Konfiguration og whitelist
# ----------------------------------------------------------------------------

@dataclass
class Config:
    token: str
    admin_chat_id: int           # primær administrator (får alarmer)
    machine_name: str
    mode: str                    # "faellestraad" | "enkelte"
    media_dir: Path
    whitelist_path: Path
    update_url: str = ""
    admin_ids: list = field(default_factory=list)  # alle, der må styre botten
    ukendte: list = field(default_factory=list)    # stavefejl i config.json
    replies: list = field(default_factory=lambda: list(DEFAULT_REPLIES))
    font_size: int = 28          # "skrift" i config — hæv for svagtseende
    theme: str = "varm"          # "tema": varm|telegram|kontrast|gul|lys|sort|moerk
    bold: bool = False           # "fed": fed beskedtekst (til svagtseende)
    keys: list = field(default_factory=list)   # "taster": genvejstaster
    show_buttons: bool = False   # "vis_knapper": vis knapraden på skærmen.
                                 # STANDARD ER FRA. Svarteksterne skrives
                                 # fysisk over tasterne på maskinen, og så
                                 # var raden en gentagelse, der tog plads
                                 # fra beskederne og billederne.
                                 # Sæt true på en TOUCH-skærm — der er
                                 # knapperne ikke en gentagelse, men den
                                 # eneste måde at svare på.
    text_width: float = 0.66     # "tekstbredde": andel af skærmen (0.1-1.0)
    bubbles: bool = True         # "bobler": beskeder i bobler med kant
    stripe: int = 16             # "stribe": stribens bredde i px (0 = ingen)
    colors: dict = field(default_factory=dict)   # "farver": overskriv enkelte
    margin: int = 40             # "sidemargen": luft i px i hver side
    blink: bool = True           # "blink": dæmpet puls ved ny besked
    text_input: bool = False     # udledes af "betjening" (se load)
    nat: tuple = (NAT_START, NAT_SLUT)  # "nat": [sluk-time, tænd-time]
    lysstyrke: int = 100         # "lysstyrke": baglyset om dagen i procent
                                 # af panelets maksimum.
                                 #
                                 # FULD STYRKE ER IKKE MEST LÆSBART. Målt
                                 # på maskine 02 (T470s, TN-panel) den
                                 # 28.09: 50 % var tydeligt lettere at
                                 # læse på tre meters afstand end 100 %.
                                 # Fuldt baglys vasker det sorte ud, så
                                 # teksten træder mindre frem — og det er
                                 # kontrasten, aldersøjne læser efter, ikke
                                 # lysmængden.
                                 #
                                 # Sættes pr. maskine: to genbrugsskærme
                                 # er sjældent ens. Standard 100, så
                                 # maskiner i drift ikke ændrer sig af sig
                                 # selv ved en opdatering.
    autosend: int = IDLE_RESET_SEC   # "autosend": sek. uden tastetryk før en
                                 # ikke-sendt besked afsendes selv (0 = fra).
                                 # Samme 5 minutter som scroll-til-bunden —
                                 # rytmen er kendt fra 2.1.6-maskinerne

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        raw = json.loads(path.read_text(encoding="utf-8"))
        media_dir = Path(raw.get("media_dir", "/var/lib/livline/media"))
        media_dir.mkdir(parents=True, exist_ok=True)
        mode = raw.get("mode", "faellestraad")
        if mode not in ("faellestraad", "enkelte"):
            raise ValueError(f"Ukendt mode: {mode}")

        # "betjening" bestemmer, hvordan brugeren svarer. Knapper og
        # skrivefelt udelukker hinanden som standard, så skærmen kun viser
        # det, den enkelte bruger kan bruge.
        betjening = raw.get("betjening", "knapper")
        if betjening not in ("knapper", "tastatur"):
            raise ValueError(
                f"Ukendt betjening: {betjening} (brug 'knapper' eller 'tastatur')")
        svar = [] if betjening == "tastatur" else \
            list(raw.get("svar", DEFAULT_REPLIES))[:9]
        # Genvejstaster: standarden følger DEFAULT_KEYS og kan sættes frit
        # med "taster". Er der flere svar end taster, fyldes der op med tal
        # — hellere en tast, der virker, end et svar, ingen kan sende.
        taster = [str(t) for t in raw.get("taster", [])][:len(svar)]
        while len(taster) < len(svar):
            i = len(taster)
            taster.append(DEFAULT_KEYS[i] if i < len(DEFAULT_KEYS)
                          else str(i + 1))
        # "admin_chat_id" må være ét tal eller en liste. Første er primær og
        # modtager alarmer; alle på listen kan bruge kommandoerne. En
        # stedfortræder kan dermed overtage, hvis administrator er væk.
        adm = raw["admin_chat_id"]
        adm_liste = [int(a) for a in (adm if isinstance(adm, list) else [adm])]
        return cls(
            token=raw["token"],
            admin_chat_id=adm_liste[0],
            admin_ids=adm_liste,
            machine_name=raw.get("machine_name", socket.gethostname()),
            mode=mode,
            media_dir=media_dir,
            whitelist_path=Path(raw.get("whitelist_path",
                                        "/var/lib/livline/whitelist.json")),
            update_url=raw.get("update_url", ""),
            ukendte=sorted(set(raw) - KENDTE_FELTER),
            replies=svar,
            keys=taster,
            show_buttons=bool(raw.get("vis_knapper", False)),
            text_width=min(1.0, max(0.1, float(raw.get("tekstbredde", 0.66)))),
            bubbles=bool(raw.get("bobler", True)),
            stripe=int(raw.get("stribe", 16)),
            font_size=int(raw.get("skrift", 28)),
            theme=raw.get("tema", "varm"),
            bold=bool(raw.get("fed", False)),
            colors=dict(raw.get("farver", {})),
            margin=int(raw.get("sidemargen", 40)),
            blink=bool(raw.get("blink", True)),
            text_input=(betjening == "tastatur"),
            nat=_nattetider(raw.get("nat")),
            autosend=max(0, int(raw.get("autosend", IDLE_RESET_SEC))),
            lysstyrke=_lysstyrke(raw.get("lysstyrke")),
        )


def _lysstyrke(raw) -> int:
    """Læser "lysstyrke" i procent og kontrollerer tallet.

    0 ville slukke skærmen helt om dagen — en maskine, der ser død ud, og
    som brugeren ikke kan trykke sig ud af. Derfor er 1 det laveste, der
    tages imod, og en fejl siges HØJT i stedet for at falde stille tilbage.
    """
    if raw is None:
        return 100
    try:
        v = int(raw)
    except (TypeError, ValueError) as e:
        log.warning('Ugyldig "lysstyrke": %r (%s) — bruger 100 %%', raw, e)
        return 100
    if not 1 <= v <= 100:
        log.warning('Ugyldig "lysstyrke": %r (skal være mellem 1 og 100) '
                    "— bruger 100 %%", raw)
        return 100
    return v


def _nattetider(raw) -> tuple[int, int]:
    """Læser "nat": [sluk, tænd] fra config og kontrollerer tallene.

    En forkert opsætning må ALDRIG falde stille tilbage — den fejl har
    kostet os en dag før, da "taster" manglede og appen tav om det. Her
    siges det højt i loggen, og /indstillinger viser altid det, maskinen
    FAKTISK bruger, ikke det, der står i filen."""
    if raw is None:
        return (NAT_START, NAT_SLUT)
    try:
        start, slut = (int(x) for x in raw)
        if not (0 <= start <= 23 and 0 <= slut <= 23):
            raise ValueError("timer skal være mellem 0 og 23")
        if start == slut:
            raise ValueError("sluk- og tændetid må ikke være ens")
        return (start, slut)
    except Exception as e:
        log.warning('Ugyldig "nat": %r (%s) — bruger [%d, %d]',
                    raw, e, NAT_START, NAT_SLUT)
        return (NAT_START, NAT_SLUT)


def skriv_sikkert(sti: Path, indhold: str) -> None:
    """Skriver en fil atomisk: først til .tmp, derefter et navneskift.
    Et navneskift kan ikke afbrydes halvvejs, så en strømafbrydelse midt i
    en skrivning kan ikke efterlade whitelist eller historik ulæselig."""
    sti.parent.mkdir(parents=True, exist_ok=True)
    tmp = sti.with_suffix(sti.suffix + ".tmp")
    tmp.write_text(indhold, encoding="utf-8")
    os.replace(tmp, sti)


class Whitelist:
    """chat_id (int) -> visningsnavn. Rækkefølgen bestemmer F-tasterne.
    Persisteres så /tilfoej overlever genstart."""

    def __init__(self, path: Path):
        self.path = path
        self._d: dict[int, str] = {}
        if path.exists():
            self._d = {int(k): v for k, v in
                       json.loads(path.read_text(encoding="utf-8")).items()}

    def __contains__(self, chat_id: int) -> bool:
        return chat_id in self._d

    def get(self, chat_id: int, default: str = "?") -> str:
        return self._d.get(chat_id, default)

    def items(self):
        return list(self._d.items())

    def ids(self) -> list[int]:
        return list(self._d.keys())

    def __len__(self):
        return len(self._d)

    def add(self, chat_id: int, name: str) -> None:
        self._d[chat_id] = name
        self._save()

    def remove(self, chat_id: int) -> bool:
        if chat_id in self._d:
            del self._d[chat_id]
            self._save()
            return True
        return False

    def _save(self) -> None:
        skriv_sikkert(self.path,
                      json.dumps({str(k): v for k, v in self._d.items()},
                                 ensure_ascii=False, indent=2))

# ----------------------------------------------------------------------------
# Beskedmodel (bot-tråd -> UI-tråd)
# ----------------------------------------------------------------------------

@dataclass
class Incoming:
    sender_name: str
    chat_id: int
    kind: str                    # "text" | "photo" | "voice" | "video"
    text: str = ""
    file_path: Path | None = None
    received: datetime = field(default_factory=datetime.now)

# ----------------------------------------------------------------------------
# Bot-lag (baggrundstråd)
# ----------------------------------------------------------------------------

_historik_laas = threading.Lock()


def gem_i_historik(sti: Path, m: "Incoming", egen: bool = False) -> None:
    """Skriver én besked til historikken. Kaldes ved MODTAGELSEN (ikke når
    beskeden tegnes), så intet går tabt, hvis programmet genstartes lige
    efter — Telegram leverer aldrig samme besked to gange.

    LÅSEN er nødvendig, fordi funktionen kaldes fra TO tråde: bot-tråden
    ved indgående beskeder, og UI-tråden ved brugerens egne svar. Hver
    skrivning er et læs-ret-skriv af hele filen, og uden lås kan de to
    flettes sammen sådan her:

        bot læser (10 beskeder) → UI læser (10) → bot skriver (11)
        → UI skriver (11, men uden bottens nye)

    Resultatet er en besked, der forsvinder ud af historikken. Den er
    stadig på skærmen, indtil maskinen genstarter — og så er den væk.
    Selve skrivningen er atomisk (os.replace); det er læsningen forinden,
    der ikke var beskyttet."""
    with _historik_laas:
        try:
            rows = []
            if sti.exists():
                rows = json.loads(sti.read_text(encoding="utf-8"))
            rows.append({"navn": m.sender_name, "chat_id": m.chat_id,
                         "type": m.kind, "tekst": m.text,
                         "fil": str(m.file_path) if m.file_path else None,
                         "tid": m.received.isoformat(), "egen": egen})
            skriv_sikkert(sti,
                          json.dumps(rows[-HISTORY_MAX:], ensure_ascii=False))
        except Exception as e:
            log.warning("Kunne ikke gemme historik: %s", e)


class BotWorker:
    def __init__(self, config: Config, whitelist: Whitelist,
                 inbox: "queue.Queue[Incoming]"):
        self.config = config
        self.whitelist = whitelist
        self.inbox = inbox
        self.loop: asyncio.AbstractEventLoop | None = None
        self.app: Application | None = None
        self.started = time.monotonic()
        self._notified_unknown: set[int] = set()  # undgå admin-spam
        self._afventer: dict[int, str] = {}       # chat_id -> navn, venter på godkendelse
        self._send_fejl: set[int] = set()         # hvem vi har meldt som uopnåelig
        # Netvagten. Tidspunktet for sidste bekræftede kontakt med Telegram.
        # Sat til "nu" ved opstart, så skærmen ikke råber, før vagten har
        # nået at prøve første gang.
        self.sidste_net_ok: float = time.monotonic()
        self.net_vaek_siden: float | None = None   # sat, når udfaldet begyndte

    def start(self) -> None:
        threading.Thread(target=self._run, name="bot", daemon=True).start()
        threading.Thread(target=self._netvagt, name="netvagt",
                         daemon=True).start()

    def _netvagt(self) -> None:
        """Holder øje med, om Telegram overhovedet kan nås.

        HVORFOR DEN FINDES: er nettet væk, ser skærmen præcis ud som en
        skærm, hvor familien ikke har skrevet. Den ældre kan ikke se
        forskel — og familien kan heller ikke, for deres beskeder ser
        afsendte ud i Telegram.
        
        Set i virkeligheden (29.09): Ulrik var hos sine forældre på et
        andet net og undrede sig over, at maskinen ikke virkede. Han har
        bygget den. Erland ville aldrig kunne gennemskue det.
        
        Vagten står for sig selv og spørger ikke python-telegram-bot om
        noget: den åbner en forbindelse til api.telegram.org og lukker
        den igen. Så virker den også, mens bot-laget er ved at genstarte
        sig selv efter en fejl."""
        while True:
            try:
                s = socket.create_connection(("api.telegram.org", 443),
                                             timeout=5)
                s.close()
                if self.net_vaek_siden is not None:
                    vaek = time.monotonic() - self.net_vaek_siden
                    log.info("Forbindelsen er tilbage efter %d min %d sek",
                             int(vaek // 60), int(vaek % 60))
                    self.net_vaek_siden = None
                self.sidste_net_ok = time.monotonic()
            except OSError as e:
                if self.net_vaek_siden is None:
                    self.net_vaek_siden = time.monotonic()
                    log.warning("Ingen forbindelse til Telegram: %s", e)
            time.sleep(NET_TJEK_SEK)

    def net_nede_sek(self) -> float:
        """Hvor længe der har været stille. 0 betyder: forbindelsen er i orden."""
        return max(0.0, time.monotonic() - self.sidste_net_ok)

    def _run(self) -> None:
        # ROBUSTHED: crash-exit uden netværk ville udløse run.sh's
        # rollback-tæller. Derfor: vent på netværk, og prøv selv igen ved
        # fejl i stedet for at lade processen dø.
        while True:
            self._wait_for_network()
            loop = None
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self.loop = loop
                self.app = self._build_app()
                # stop_signals=None: signalhåndtering virker kun i hovedtråden
                self.app.run_polling(stop_signals=None,
                                     drop_pending_updates=False)
                return  # normal nedlukning
            except Exception as e:
                log.error("Bot-laget fejlede: %s — nyt forsøg om 30 s", e)
                time.sleep(30)
            finally:
                # Hver runde laver en ny event-løkke. Lukkes den gamle ikke,
                # bliver dens filbeskrivere hængende — og en maskine, der
                # mister netværket mange gange på en dag, løber til sidst
                # tør. Fejlen ville vise sig som "for mange åbne filer",
                # timer efter den egentlige årsag.
                self.loop = None
                if loop is not None:
                    try:
                        loop.close()
                    except Exception:
                        # TAVSHED MED VILJE — den eneste i filen.
                        # Vi er ved at rydde op efter en løkke, der allerede
                        # er død. At oprydningen fejler, kan der ikke gøres
                        # noget ved, og en advarsel her ville komme oven i
                        # den rigtige fejl og skjule den.
                        pass

    def _wait_for_network(self) -> None:
        """Bloker til Telegrams API kan nås (fx mens WiFi kommer op ved boot)."""
        while True:
            try:
                s = socket.create_connection(("api.telegram.org", 443), timeout=5)
                s.close()
                return
            except OSError:
                log.info("Venter på netværk…")
                time.sleep(10)

    def _build_app(self) -> Application:
        app = (Application.builder().token(self.config.token)
               .post_init(self._post_init).build())
        admin = filters.Chat(chat_id=self.config.admin_ids)
        # /start har MED VILJE ingen admin-filter: det er den kommando, en
        # helt fremmed trykker på for at bede om adgang. Alle de øvrige er
        # kun for administrator.
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("status", self._cmd_status, admin))
        app.add_handler(CommandHandler("tilfoej", self._cmd_add, admin))
        app.add_handler(CommandHandler("fjern", self._cmd_remove, admin))
        app.add_handler(CommandHandler("liste", self._cmd_list, admin))
        app.add_handler(CommandHandler("opdater", self._cmd_update, admin))
        app.add_handler(CommandHandler("skaerm", self._cmd_screenshot, admin))
        app.add_handler(CommandHandler("indstillinger", self._cmd_settings, admin))
        app.add_handler(CommandHandler("hjaelp", self._cmd_help, admin))
        app.add_handler(CallbackQueryHandler(self._on_godkend, pattern=r"^godkend:"))
        app.add_handler(MessageHandler(~filters.COMMAND, self._on_message))
        return app

    def _er_nat(self, naar: datetime | None = None) -> bool:
        """Samme regel som skærmens nattetilstand. Ligger også her, fordi
        bot-laget skal kunne tie om natten uden at kende til vinduet."""
        start, slut = self.config.nat
        t = (naar or datetime.now()).hour
        return t >= start or t < slut

    async def _post_init(self, app: Application) -> None:
        # TAVS OM NATTEN. Maskinen genstarter kl. 03 for at få en frisk
        # start — og uden det her ville den sende "✅ startede" til din
        # telefon hver eneste nat kl. 03. Det daglige livstegn kommer i
        # stedet kl. 8, når skærmen tændes igen (se _nat_vagt).
        if self._er_nat():
            log.info("Startbesked udeladt — det er nat")
            return
        try:
            besked = (f"✅ {self.config.machine_name} startede "
                      f"(v{VERSION}, {self.config.mode}).")
            # Advar om opsætning, der ser rigtig ud, men ikke gør det den skal
            if self.config.ukendte:
                besked += ("\n⚠️ Ukendte felter i config (stavefejl?): "
                           + ", ".join(self.config.ukendte))
            if not self.config.replies and not self.config.text_input:
                besked += ("\n⚠️ Brugeren kan ikke svare: hverken faste svar "
                           "eller skrivefelt er slået til.")
            besked += self._privatlivsadvarsel()
            besked += self._tastadvarsel()
            besked += "\nSe hele opsætningen med /indstillinger"
            await app.bot.send_message(self.config.admin_chat_id, besked)
        except Exception as e:
            log.warning("Kunne ikke sende startbesked til admin: %s", e)

    async def _on_godkend(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Godkender en person, når administrator trykker på knappen."""
        q = update.callback_query
        await q.answer()
        # Kun administrator må godkende. Knappen sendes ganske vist kun til
        # administrator, men et videresendt tryk skal heller ikke virke.
        if q.from_user.id not in self.config.admin_ids:
            await q.edit_message_text("Kun administrator kan godkende.")
            return
        try:
            chat_id = int(q.data.split(":", 1)[1])
        except (IndexError, ValueError):
            return
        navn = self._afventer.pop(chat_id, str(chat_id))
        self.whitelist.add(chat_id, navn)
        self._notified_unknown.discard(chat_id)
        await q.edit_message_text(
            f"✅ Tilføjet: {navn} ({chat_id})\n"
            f"Ret navnet med /tilfoej {chat_id} <nyt navn> — det er navnet, "
            f"der står på skærmen." + self._tastadvarsel())
        try:
            await context.bot.send_message(
                chat_id, f"Du er nu forbundet til {self.config.machine_name}. "
                         "Alt hvad du sender her, vises på skærmen.")
        except Exception as e:
            # HUN SKAL VIDE, AT HUN ER MED.
            # Her stod "pass". Fejlede bekræftelsen, fik den nye person
            # aldrig at vide, at hun var godkendt — og administrator troede,
            # hun var i gang. Hun skriver ikke, fordi hun ikke ved, hun må.
            log.warning("Kunne ikke bekræfte over for %s: %s", chat_id, e)
            await update.effective_message.reply_text(
                f"⚠️ Tilføjet, men kunne IKKE sige det til {chat_id}.\n"
                f"Grund: {e}\n"
                f"Hun ved ikke, at hun er med. Sig det selv, eller bed "
                f"hende skrive til botten.")

    def _tema_note(self) -> str:
        """Et tema, maskinen ikke kender, bruges ikke — den falder tilbage
        til "varm". Uden denne note ville /indstillinger vise det ønskede
        tema, mens skærmen brugte et andet: maskinen ser rigtig ud og gør
        noget andet. Præcis den fejltype, /indstillinger blev bygget imod."""
        if self.config.theme in THEMES:
            return ""
        return f"  ⚠️ findes ikke (kendte: {', '.join(sorted(THEMES))})"

    def _tastadvarsel(self) -> str:
        """Advarer, når nogen er tilføjet ud over de fem F-taster.

        I enkelte-tilstand kan brugeren kun HENTE en samtale frem med en
        F-tast, og der er fem. Person nummer seks kan skrive, men brugeren
        kan ikke gå ind i samtalen af sig selv — hun kan kun svare, hvis
        vedkommende tilfældigvis skrev sidst. Uden denne advarsel opdages
        det først, når nogen undrer sig over aldrig at få svar."""
        if self.config.mode != "enkelte":
            return ""
        antal = len(self.whitelist)
        if antal <= len(FKEYS):
            return ""
        uden = antal - len(FKEYS)
        return (f"\n\n⚠️ {antal} personer på listen, men kun {len(FKEYS)} "
                f"F-taster. De {uden} sidste kan skrive, men brugeren kan "
                f"ikke selv hente deres samtale frem. Se rækkefølgen med "
                f"/liste — den er det, der bestemmer tasterne.")

    def _privatlivsadvarsel(self) -> str:
        """Advarer, hvis en administrator også står på whitelisten.

        I fællestråd sendes hver besked videre til ALLE på whitelisten. Står
        du selv der — typisk fordi du tilføjede dig selv for at teste — sidder
        du med i familiens private samtale uden at have taget stilling til det.
        Ingen kan se det på skærmen, og familien opdager det ikke.

        Administrator behøver ikke stå på whitelisten: admin_chat_id giver
        alarmer og kommandoer, whitelisten er dem, der er MED i samtalen."""
        if self.config.mode != "faellestraad":
            return ""
        med = [i for i in self.config.admin_ids if i in self.whitelist.ids()]
        if not med:
            return ""
        navne = ", ".join(self.whitelist.get(i, str(i)) for i in med)
        return ("\n\n🔒 Privatliv: administrator står på whitelisten "
                f"({navne}) og modtager derfor familiens beskeder på "
                "telefonen. Skal maskinen leveres, så fjern med /fjern — "
                "du beholder alarmer og kommandoer.")

    # -- dagligt livstegn og status ---------------------------------------------------

    def _status_text(self) -> str:
        up = int(time.monotonic() - self.started)
        d, rem = divmod(up, 86400)
        h, rem = divmod(rem, 3600)
        m = rem // 60
        du = shutil.disk_usage("/")
        linjer = [f"{self.config.machine_name} (v{VERSION}, {self.config.mode})",
                  f"Oppetid: {d} d {h} t {m} min",
                  f"Disk: {du.free / 1e9:.1f} GB fri af {du.total / 1e9:.1f} GB",
                  f"Whitelist: {len(self.whitelist)} personer"]
        # FORBINDELSEN. Står /status til at svare, er den i orden lige nu —
        # men et udfald, der lige er overstået, er værd at kende: det
        # forklarer beskeder, der kom for sent, og en tavs formiddag.
        nede = self.net_nede_sek()
        if nede > NET_STILLE_SEK:
            linjer.append(f"⚠️ Ingen forbindelse i {int(nede // 60)} min "
                          f"— skærmen siger det selv")
        elif self.net_vaek_siden is not None:
            linjer.append("⚠️ Forbindelsen er ustabil lige nu")
        else:
            linjer.append("Forbindelse: i orden")
        # Hvor længe siden familien sidst skrev. Teknisk drift kan være
        # perfekt, mens brugen falder — og tavshed er det første tegn på,
        # at en maskine er ved at blive overflødig.
        try:
            rows = json.loads((self.config.whitelist_path.parent /
                               "historik.json").read_text(encoding="utf-8"))
            modtaget = [r for r in rows if not r.get("egen")]
            if modtaget:
                sidst = datetime.fromisoformat(modtaget[-1]["tid"])
                dage = (datetime.now() - sidst).days
                linjer.append(
                    "Sidste besked fra familien: "
                    + ("i dag" if dage == 0 else f"{dage} dage siden")
                    + ("  ⚠️ ring til familien" if dage >= 14 else ""))
        except Exception as e:
            # EN MANGLENDE LINJE LIGNER GODE NYHEDER.
            # Her stod "pass". Kunne historikken ikke læses, forsvandt
            # linjen om, hvor længe siden familien sidst skrev — og et
            # /status uden advarsler ser ud, som om alt er i orden.
            # Netop den linje er den vigtigste: en maskine, der virker
            # perfekt og ikke bliver brugt, er også en fejl.
            log.warning("Kunne ikke læse historikken til /status: %s", e)
            linjer.append("⚠️ Kunne ikke læse historikken — "
                          "ved ikke, hvornår familien sidst skrev")
        # Hardware skrives dagligt af et cron-job (root), så en døende disk
        # eller et udslidt batteri opdages hjemmefra
        try:
            hw = json.loads((self.config.whitelist_path.parent /
                             "hardware.json").read_text(encoding="utf-8"))
            if hw.get("batteri") is not None:
                b = hw["batteri"]
                linjer.append(f"Batteri: {b} % af oprindelig kapacitet"
                              + ("  ⚠️ overvej udskiftning" if b < 70 else ""))
            if hw.get("disk_smart"):
                s = hw["disk_smart"]
                linjer.append(f"Disk-helbred: {s}"
                              + ("" if s == "PASSED" else "  ⚠️ udskift disken"))
            if hw.get("opdateringer"):
                linjer.append(f"Systemopdateringer venter: {hw['opdateringer']}"
                              "  (sikkerhed er allerede installeret)")
        except Exception as e:
            # Samme fælde: uden disse linjer siger /status intet om batteri
            # og disk — og tavshed læses som "alt er godt". En døende disk
            # ville forsvinde ud af rapporten netop når den betød mest.
            log.warning("Kunne ikke læse hardware-tjekket til /status: %s", e)
            linjer.append("⚠️ Kunne ikke læse hardware-tjekket — "
                          "intet om batteri og disk i dag")
        return "\n".join(linjer)

    # -- admin-kommandoer --------------------------------------------------------

    async def _cmd_status(self, update: Update, _):
        await update.effective_message.reply_text("📊 " + self._status_text())

    async def _cmd_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            chat_id = int(context.args[0])
            name = " ".join(context.args[1:]).strip()
            assert name
        except (IndexError, ValueError, AssertionError):
            await update.effective_message.reply_text(
                "Brug: /tilfoej <chat_id> <navn>\nfx: /tilfoej 111111111 Mette")
            return
        self.whitelist.add(chat_id, name)
        self._notified_unknown.discard(chat_id)
        await update.effective_message.reply_text(
            f"✅ Tilføjet: {name} ({chat_id})" + self._tastadvarsel())
        try:  # bekræft over for familiemedlemmet, hvis de har trykket /start
            await context.bot.send_message(
                chat_id, f"Du er nu forbundet til {self.config.machine_name}. "
                         "Alt hvad du sender her, vises på skærmen.")
        except Exception as e:
            # Samme som ved godkend-knappen: uden denne besked ved hun ikke,
            # at hun er med — og du tror, hun er i gang.
            log.warning("Kunne ikke bekræfte over for %s: %s", chat_id, e)
            await update.effective_message.reply_text(
                f"⚠️ Tilføjet, men kunne IKKE sige det til {chat_id}.\n"
                f"Grund: {e}\n"
                f"Vedkommende ved ikke, at hun er med. Sig det selv, eller "
                f"bed hende skrive til botten.")

    async def _cmd_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            chat_id = int(context.args[0])
        except (IndexError, ValueError):
            await update.effective_message.reply_text("Brug: /fjern <chat_id>")
            return
        name = self.whitelist.get(chat_id)
        ok = self.whitelist.remove(chat_id)
        await update.effective_message.reply_text(
            f"🗑 Fjernet: {name} ({chat_id})" if ok else f"Ukendt id: {chat_id}")

    async def _cmd_list(self, update: Update, _):
        if not len(self.whitelist):
            await update.effective_message.reply_text("Whitelisten er tom.")
            return
        lines = [f"• {FKEYS[i] if i < len(FKEYS) else '—'}: {v} — {k}"
                 for i, (k, v) in enumerate(self.whitelist.items())]
        await update.effective_message.reply_text("👪 Whitelist:\n" + "\n".join(lines))

    async def _cmd_help(self, update: Update, _):
        await update.effective_message.reply_text(
            "/status — maskinstatus\n"
            "/tilfoej <chat_id> <navn> — tilføj familiemedlem\n"
            "/fjern <chat_id> — fjern familiemedlem\n"
            "/liste — vis whitelist (med F-taster)\n"
            "/indstillinger — vis hvad maskinen faktisk bruger\n"
            "/skaerm — send et billede af brugerens skærm\n"
            "/opdater — hent og installér ny programversion\n"
            "/hjaelp — denne oversigt")

    async def _cmd_settings(self, update: Update, _):
        """Viser hvad maskinen FAKTISK bruger — ikke hvad der står i filen.
        Mangler et felt i config, bruges standarden, og det er netop den
        slags, der ellers først opdages ved at prøve tasterne på skærmen."""
        c = self.config
        if c.text_input:
            # Skrivefelt: faste svar findes ikke, så tasteoversigten ville
            # kun være støj. Til gengæld er autosend vigtig at kunne se —
            # den afgør, om en glemt besked kommer af sted af sig selv.
            auto = (f"efter {c.autosend // 60} min. ({c.autosend} sek.)"
                    if c.autosend > 0 else "fra — kun Enter sender")
            midt = ("Betjening: skrivefelt (brugeren skriver selv)\n"
                    f"Send af sig selv: {auto}\n\n")
        else:
            par = [f"{t.split('/')[0].upper()} = {s}"
                   for t, s in zip(c.keys, c.replies)] or ["(ingen faste svar)"]
            midt = ("Betjening: faste svar\n"
                    f"Knapper på skærmen: {'ja' if c.show_buttons else 'nej'}\n"
                    "Taster:\n  " + "\n  ".join(par) + "\n\n")
        tema_note = self._tema_note()
        tekst = (
            f"⚙️ {c.machine_name} (v{VERSION})\n\n"
            + midt +
            f"Tilstand: {c.mode}\n"
            f"Tema: {c.theme}{tema_note}   Skrift: {c.font_size}"
            f"{f' ({SKRIFT_PX} px)' if SKRIFT_PX else ''}"
            f"{'  (fed)' if c.bold else ''}\n"
            f"Lysstyrke: {c.lysstyrke} %"
            f"{' (fuld — prøv 50-70 %, hvis teksten er svær at læse)' if c.lysstyrke == 100 else ''}\n"
            f"Administratorer: {len(c.admin_ids)}\n"
            f"Signeret /opdater: "
            f"{'til' if NOEGLE_STI.exists() else 'fra (ingen nøgle)'}")
        if c.ukendte:
            tekst += ("\n\n⚠️ Ukendte felter i config (stavefejl?): "
                      + ", ".join(c.ukendte))
        tekst += self._privatlivsadvarsel()
        tekst += self._tastadvarsel()
        await update.effective_message.reply_text(tekst)

    async def _cmd_screenshot(self, update: Update, _):
        """Sender et skærmbillede af brugerens skærm til administrator.
        Erstatter behovet for fjernskrivebord i de fleste tilfælde."""
        fil = self.config.media_dir / "skaerm.png"
        try:
            # GNOME på Wayland: skærmbillede via Shell'ens D-Bus-tjeneste
            r = subprocess.run(
                ["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
                 "--object-path", "/org/gnome/Shell/Screenshot",
                 "--method", "org.gnome.Shell.Screenshot.Screenshot",
                 "false", "false", str(fil)],
                capture_output=True, timeout=20, text=True)
            if not fil.exists():
                raise RuntimeError(r.stderr.strip() or "intet billede")
            with open(fil, "rb") as f:
                await update.effective_message.reply_photo(
                    f, caption=f"Skærmen på {self.config.machine_name} lige nu")
        except Exception as e:
            await update.effective_message.reply_text(
                f"Kunne ikke tage skærmbillede: {e}")

    def _tjek_signatur(self, kode: str, signatur: bytes | None) -> str | None:
        """Kontrollerer, at koden er underskrevet med DIN nøgle.

        Hvorfor: syntakstjek og prøvekørsel beviser, at koden VIRKER — ikke
        at den kommer fra dig. Bliver GitHub-kontoen overtaget, ville en
        fremmed kunne lægge kode i gisten, som består begge prøver, og hver
        maskine ville installere den ved næste /opdater. Signaturen er det
        eneste tjek, der siger noget om AFSENDEREN.

        Slået fra, når der ikke ligger en offentlig nøgle på maskinen. Det
        er med vilje: en maskine i drift må ikke kunne låse sig selv ude
        fra opdateringer, fordi en nøgle mangler. Ligger nøglen der, er
        signaturen til gengæld et krav.

        Returnerer None ved godkendt, ellers en tekst, der forklarer hvorfor.
        """
        if not NOEGLE_STI.exists():
            return None                      # signering ikke slået til
        if not signatur:
            return ("der ligger en offentlig nøgle på maskinen, men den nye "
                    "version har ingen signatur. Læg en .sig-fil ved siden "
                    "af koden, eller fjern " + str(NOEGLE_STI))
        try:
            with tempfile.TemporaryDirectory() as d:
                k = Path(d) / "kode"
                s = Path(d) / "kode.sig"
                k.write_text(kode, encoding="utf-8")
                s.write_bytes(signatur)
                r = subprocess.run(
                    ["openssl", "dgst", "-sha256", "-verify", str(NOEGLE_STI),
                     "-signature", str(s), str(k)],
                    capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                return ("signaturen passer ikke til koden. Enten er filen "
                        "ændret undervejs, eller den er ikke underskrevet "
                        "med din nøgle")
            return None
        except FileNotFoundError:
            return "openssl mangler på maskinen (sudo apt install openssl)"
        except Exception as e:
            return f"signaturen kunne ikke kontrolleres: {e}"

    async def _cmd_update(self, update: Update, _):
        """Selvopdatering: download -> signatur -> syntakstjek -> prøvekørsel
        -> backup -> udskift -> genstart (run.sh starter den nye version og
        ruller tilbage til .bak ved crash-loop)."""
        reply = update.effective_message.reply_text
        if not self.config.update_url:
            await reply("Ingen update_url i konfigurationen — /opdater er slået fra.")
            return
        await reply("⬇️ Henter ny version fra update_url…")
        try:
            import httpx  # følger med python-telegram-bot
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
                r = await c.get(self.config.update_url)
                r.raise_for_status()
            code = r.text
            # Signaturen ligger ved siden af koden, med .sig sat på adressen.
            # Hentes kun, når maskinen faktisk har en nøgle at prøve den mod.
            signatur = None
            if NOEGLE_STI.exists():
                async with httpx.AsyncClient(timeout=30,
                                             follow_redirects=True) as c:
                    sr = await c.get(self.config.update_url.split("?")[0] + ".sig")
                    if sr.status_code == 200:
                        signatur = base64.b64decode(sr.text.strip(),
                                                    validate=False)
        except Exception as e:
            await reply(f"❌ Download fejlede: {e}")
            return

        problem = self._tjek_signatur(code, signatur)
        if problem:
            await reply(f"❌ Signaturen blev ikke godkendt — intet ændret:\n{problem}")
            return

        m = re.search(r'^VERSION\s*=\s*"([^"]+)"', code, re.M)
        new_ver = m.group(1) if m else "ukendt"
        target = Path(__file__).resolve()
        staging = target.with_suffix(".py.ny")
        try:
            staging.write_text(code, encoding="utf-8")
            # Syntakstjek FØR udskiftning. cfile peger på /tmp, så tjekket
            # ikke kræver skriveadgang til __pycache__ i programmappen —
            # den mappe kan være ejet af root efter en manuel kopiering.
            py_compile.compile(str(staging), doraise=True,
                               cfile="/tmp/livline_syntakstjek.pyc")
        except py_compile.PyCompileError as e:
            staging.unlink(missing_ok=True)
            await reply(f"❌ Den nye version har en syntaksfejl — intet ændret:\n{e}")
            return
        except Exception as e:
            await reply(f"❌ Kunne ikke skrive ny version (tjek filrettigheder): {e}")
            return

        # PRØVEKØRSEL i usynligt skærmmiljø: bygger den nye version rent
        # faktisk sit vindue? Syntakstjek alene fanger ikke Tk-fejl, der
        # først opstår ved tegning (det væltede 3.3-3.6).
        if shutil.which("xvfb-run"):
            try:
                # sys.executable, ikke "python3": appen kører i sit eget
                # virtuelle miljø, og systemets python kender ikke
                # python-telegram-bot. Med "python3" ville prøvekørslen
                # fejle på ALLE nye versioner — og /opdater ville se ud
                # som om enhver opdatering var defekt.
                p = subprocess.run(
                    ["xvfb-run", "-a", sys.executable, str(staging),
                     "--selftest"],
                    capture_output=True, text=True, timeout=90)
                if p.returncode != 0:
                    staging.unlink(missing_ok=True)
                    fejl = (p.stderr or p.stdout).strip().splitlines()[-3:]
                    await reply("❌ Den nye version kunne ikke starte i "
                                "prøvekørsel — intet ændret:\n" + "\n".join(fejl))
                    return
            except subprocess.TimeoutExpired:
                staging.unlink(missing_ok=True)
                await reply("❌ Prøvekørslen hang — intet ændret.")
                return
        else:
            await reply("ℹ️ xvfb mangler, så prøvekørsel blev sprunget over "
                        "(installér med: sudo apt install xvfb).")

        shutil.copy2(target, target.with_suffix(".py.bak"))  # rollback-kopi
        staging.replace(target)
        await reply(f"✅ v{VERSION} → v{new_ver} installeret. Genstarter om 2 sek. — "
                    "du får en startbesked, når den nye version kører.")
        await asyncio.sleep(2)
        os._exit(0)  # run.sh-løkken starter den nye version

    # -- indgående beskeder --------------------------------------------------------

    async def _meld_ukendt(self, bot, chat_id: int, sender: str) -> None:
        """Fortæller administrator, at en ukendt person har henvendt sig.

        Ligger for sig selv, fordi to veje fører hertil: en almindelig
        besked og /start. Stod koden to steder, ville de før eller siden
        komme til at gøre noget forskelligt — og den ene ville blive
        glemt, præcis som /start blev det.

        Kun ÉN gang pr. person. Ellers kunne en fremmed, der bliver ved
        med at skrive, fylde administrators telefon med advarsler."""
        if chat_id in self.config.admin_ids or chat_id in self._notified_unknown:
            return
        self._notified_unknown.add(chat_id)
        # Godkendelse med ÉT TRYK.
        # Før stod der blot "Godkend med: /tilfoej <id> <navn>" som tekst.
        # Telegram gør automatisk /tilfoej til et trykbart link, og et tryk
        # sender KUN kommandoen — uden id og navn. Botten svarede så
        # "Brug: /tilfoej <chat_id> <navn>", og personen blev aldrig
        # godkendt. Vi havde bygget en fælde, hvor det oplagte tryk gjorde
        # det forkerte.
        self._afventer[chat_id] = sender
        knap = InlineKeyboardMarkup([[InlineKeyboardButton(
            f"✅ Godkend {sender}", callback_data=f"godkend:{chat_id}")]])
        try:
            await bot.send_message(
                self.config.admin_chat_id,
                f"⚠️ Ukendt person skrev til {self.config.machine_name}:\n"
                f"{sender} — chat_id {chat_id}\n\n"
                f"Navnet er selvvalgt og er ikke et bevis. Godkend kun en, "
                f"du selv har bedt om at skrive.\n\n"
                f"Tryk på knappen for at godkende, eller skriv selv:\n"
                f"/tilfoej {chat_id} Mor",
                reply_markup=knap)
        except Exception as e:
            log.warning("Kunne ikke melde ukendt person til admin: %s", e)

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/start — det knappen i Telegram hedder, når man åbner en bot.

        HER LÅ EN FÆLDE. Botten havde ingen handler for /start, og
        beskedhåndteringen springer kommandoer over. Trykkede familien
        Start, skete der derfor INTET: ingen melding til administrator,
        intet svar til dem. Samtidig stod der i install.sh og i
        byggevejledningen: "bed familien trykke /start — du får en
        ⚠️-besked". Vi bad altså folk gøre noget, der ikke virkede.

        Fejlen ville have vist sig stående i en fremmed stue, hvor de
        trykker igen og igen, og du venter på en besked, der aldrig kom.

        Afsenderen får altid et svar. Tavshed er det værste, en maskine
        kan give en, der lige har gjort som man bad om."""
        msg = update.effective_message
        chat_id = update.effective_chat.id if update.effective_chat else None
        if msg is None or chat_id is None:
            return
        sender = update.effective_user.full_name if update.effective_user else "?"

        if chat_id in self.config.admin_ids:
            await msg.reply_text(f"{self.config.machine_name} — v{VERSION}.\n"
                                 f"Skriv /hjaelp for kommandoerne.")
            return

        if chat_id in self.whitelist:
            await msg.reply_text(
                "Du er med. Skriv en besked, så står den på skærmen.")
            return

        log.warning("/start fra ukendt chat_id=%s (%s)", chat_id, sender)
        await self._meld_ukendt(context.bot, chat_id, sender)
        await msg.reply_text(
            "Tak. Der er givet besked om, at du gerne vil med.\n"
            "Så snart du er godkendt, står dine beskeder på skærmen.")

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.effective_message
        chat_id = update.effective_chat.id if update.effective_chat else None
        if msg is None or chat_id is None:
            return

        # SIKKERHED: botten er offentligt søgbar — kun whitelist vises på skærmen
        if chat_id not in self.whitelist:
            sender = update.effective_user.full_name if update.effective_user else "?"
            log.warning("Afvist besked fra ukendt chat_id=%s (%s)", chat_id, sender)
            await self._meld_ukendt(context.bot, chat_id, sender)
            return

        name = self.whitelist.get(chat_id)

        if msg.text:
            self._modtag(Incoming(name, chat_id, "text", text=msg.text))
        elif msg.photo:
            path = await self._download(msg.photo[-1].file_id, context, ".jpg")
            self._modtag(Incoming(name, chat_id, "photo",
                                  text=msg.caption or "", file_path=path))
        elif msg.voice or msg.audio:
            # TALEBESKEDER AFSPILLES IKKE LÆNGERE. Samme begrundelse som
            # video, og truffet samme dag.
            #
            # En talebesked starter af sig selv, kan ikke standses med de
            # otte taster, og lyder forskelligt alt efter, hvornår på
            # døgnet den kommer — kl. 2 om natten fyldte den hele
            # lejligheden. Dertil: i den aldersgruppe bruges høreapparater,
            # og en højttaler i en stue er den dårligste måde at høre en
            # besked på. Telefonen gør det bedre.
            #
            # LIVLINE ER SKÆRM OG TASTATUR. Lyd er telefonens arbejde.
            hvad = "talebesked" if msg.voice else "musikfil"
            # LINJEN PÅ SKÆRMEN SKAL SIGE DET SAMME SOM SVARET.
            # Stod der kun "(Anne sendte en talebesked)", ville han sidde
            # og vente på, at den begyndte. Sætningen skal være der, hvor
            # han kigger — ikke kun på hendes telefon.
            self._modtag(Incoming(name, chat_id, "text",
                                  text=f"({name} sendte en {hvad} "
                                       f"— kan desværre ikke vises her)"))
            try:
                await msg.reply_text(
                    f"🎙 {hvad.capitalize()}en kan desværre ikke afspilles "
                    f"på Livline-skærmen.\n"
                    f"Jeg har sendt den videre til de andre i familien.\n"
                    f"Skriv gerne et par ord i stedet.")
            except Exception as e:
                log.warning("Kunne ikke svare om talebesked til %s: %s",
                            chat_id, e)
            if self.config.mode == "faellestraad":
                await self._rebroadcast(msg, name, exclude=chat_id)
            return
        elif msg.video or msg.video_note:
            # VIDEO VISES IKKE LÆNGERE PÅ SKÆRMEN.
            #
            # Afspilleren tog hele skærmen OG tastaturet: mpv binder selv
            # q til "luk" og pilene til at spole. Mens en video kørte,
            # gjorde de otte taster på tastaturdækket altså noget helt
            # andet end det, der stod på papiret — Q lukkede videoen i
            # stedet for at sende "Tak".
            #
            # For en mand med demens er en tast, der skifter betydning,
            # værre end en funktion, der mangler. Videoen når stadig
            # familien på deres telefoner; det er kun skærmen i stuen,
            # der ikke viser den.
            #
            # Filen hentes derfor slet ikke ned. Det fjerner samtidig
            # downloadfejl, diskforbrug og to afspillere oven i hinanden.
            self._modtag(Incoming(name, chat_id, "text",
                                  text=f"({name} sendte en video "
                                       f"— kan desværre ikke vises her)"))
            try:
                await msg.reply_text(
                    "🎬 Videoen kan desværre ikke vises på "
                    "Livline-skærmen.\n"
                    "Jeg har sendt den videre til de andre i familien.\n"
                    "Skriv gerne et par ord om, hvad den viser.")
            except Exception as e:
                log.warning("Kunne ikke svare om video til %s: %s", chat_id, e)
            if self.config.mode == "faellestraad":
                await self._rebroadcast(msg, name, exclude=chat_id)
        else:
            # Alt andet (stickers, GIF'er, dokumenter, lokationer, kontakter)
            # blev tidligere ignoreret lydløst — familien så "leveret", mens
            # intet nåede skærmen. Nu vises i det mindste, at der kom noget.
            hvad = ("en sticker" if msg.sticker else
                    "en GIF" if msg.animation else
                    "en fil" if msg.document else
                    "et sted på kortet" if msg.location else
                    "et kontaktkort" if msg.contact else
                    "en musikfil" if msg.audio else None)
            if hvad is None:
                return
            self._modtag(Incoming(name, chat_id, "text",
                                  text=f"({name} sendte {hvad})"))
            # HER STOD ET return. Skærmen fik sin linje, men de ØVRIGE i
            # fællestråden fik ingenting — og ingen fik det at vide.
            #
            # Barnebarnet sender en GIF. Farmor ser "(Emil sendte en GIF)"
            # på skærmen. Datteren ser intet og aner ikke, at der har været
            # kontakt. Løftet i fællestråd er, at alle ser alt.
            #
            # Telefonerne KAN vise en GIF, selvom skærmen ikke kan. Så de
            # får den ægte vare; det er kun skærmen, der får en linje.

        # FÆLLESTRÅD: genudsend til de øvrige godkendte, så alle ser alt.
        # Medier genudsendes via file_id — ingen ekstra download/upload.
        if self.config.mode == "faellestraad":
            await self._rebroadcast(msg, name, exclude=chat_id)

    async def _rebroadcast(self, msg, sender_name: str, exclude: int,
                           note: str | None = None) -> None:
        """Sender videre til de øvrige i fællestråden.

        note: send denne linje i stedet for selve beskeden. Bruges, når der
        ikke er noget at sende videre — fx en video, der var for stor. De
        øvrige skal stadig vide, at der HAR været kontakt.

        Medierne sendes videre med file_id, så Telegram flytter dem selv;
        maskinen henter og uploader ikke noget.

        SIDSTE UDVEJ er en linje tekst. Tavshed er ikke et alternativ: i
        fællestråd tror alle, at de ser alt, og den tro er hele produktet."""
        for other_id in self.whitelist.ids():
            if other_id == exclude:
                continue
            try:
                b = self.app.bot
                fra = f"Fra {sender_name}"
                if note:
                    await b.send_message(other_id, f"{sender_name} {note}")
                elif msg.text:
                    await b.send_message(other_id, f"{sender_name}: {msg.text}")
                elif msg.photo:
                    await b.send_photo(
                        other_id, msg.photo[-1].file_id,
                        caption=fra + (f": {msg.caption}" if msg.caption else ""))
                elif msg.voice:
                    await b.send_voice(other_id, msg.voice.file_id, caption=fra)
                elif msg.video:
                    await b.send_video(
                        other_id, msg.video.file_id,
                        caption=fra + (f": {msg.caption}" if msg.caption else ""))
                elif msg.video_note:
                    await b.send_video_note(other_id, msg.video_note.file_id)
                elif msg.sticker:
                    await b.send_sticker(other_id, msg.sticker.file_id)
                elif msg.animation:
                    await b.send_animation(other_id, msg.animation.file_id,
                                           caption=fra)
                elif msg.document:
                    await b.send_document(other_id, msg.document.file_id,
                                          caption=fra)
                elif msg.audio:
                    await b.send_audio(other_id, msg.audio.file_id, caption=fra)
                else:
                    # Kort, kontaktkort og alt, vi ikke har en knap til.
                    # Hellere en linje for lidt end tavshed.
                    await b.send_message(
                        other_id,
                        f"{sender_name} sendte noget, Livline ikke kan sende "
                        f"videre. Skriv til {sender_name}, hvis det haster.")
                self._send_fejl.discard(other_id)
            except Exception as e:  # fx medlem der aldrig har trykket /start
                log.warning("Genudsendelse til %s fejlede: %s", other_id, e)
                # Samme melding som ved almindelig afsendelse. Før stod det
                # kun i loggen, og en blokeret modtager forsvandt lydløst
                # ud af familiens samtale.
                await self._meld_afsendelsesfejl(other_id, e)

    def _modtag(self, m: Incoming) -> None:
        """Gemmer beskeden i historikken FØRST og lægger den derefter i køen
        til skærmen. Rækkefølgen er vigtig: bliver programmet afbrudt (fx af
        /opdater) lige efter modtagelsen, er beskeden allerede gemt."""
        gem_i_historik(self.config.whitelist_path.parent / "historik.json", m)
        self.inbox.put(m)

    async def _download(self, file_id: str, context, suffix: str) -> Path:
        tg_file = await context.bot.get_file(file_id)
        dest = self.config.media_dir / f"{file_id[:32]}{suffix}"
        await tg_file.download_to_drive(dest)
        return dest

    # -- udgående (kaldes fra UI-tråden) -----------------------------------------

    def send_admin(self, tekst: str) -> None:
        """Sender til administrator uden at gå gennem whitelisten."""
        self.send_text([self.config.admin_chat_id], tekst)

    async def _meld_afsendelsesfejl(self, chat_id: int, fejl: Exception) -> None:
        """Fortæller administrator, at en besked IKKE nåede frem.

        Her lå den tavseste fejl i hele maskinen. Afsendelsen tager
        modtagerne én ad gangen og melder "det gik godt", hvis bare ÉN
        lykkedes. Fejlede den for de øvrige, stod det kun i loggen.

        SET I DRIFT: en pårørende kan BLOKERE botten i Telegram — ved et
        uheld, eller mens hun rydder op. Så kan maskinen aldrig skrive til
        hende igen. Hun får ingen beskeder fra sin far og opdager det ikke,
        for der kommer jo bare ingenting. Han ser, at hun ikke skriver.
        Hun tror, han ikke svarer. Og ingen af dem kan se hvorfor.

        Kun ÉN melding pr. person, indtil det lykkes igen. En telefon, der
        er slukket i en uge, må ikke fylde administrators skærm."""
        if chat_id in self._send_fejl or chat_id in self.config.admin_ids:
            return
        self._send_fejl.add(chat_id)
        navn = self.whitelist.get(chat_id) or str(chat_id)
        try:
            await self.app.bot.send_message(
                self.config.admin_chat_id,
                f"⚠️ {self.config.machine_name} kunne ikke skrive til "
                f"{navn} ({chat_id}).\n"
                f"Grund: {fejl}\n\n"
                f"{navn} får ingen beskeder og kan ikke selv se det. "
                f"Den hyppigste årsag er, at botten er blokeret i Telegram: "
                f"bed hende åbne samtalen med botten og ophæve blokeringen.\n\n"
                f"Meldes kun én gang — næste melding kommer først, når det "
                f"har virket igen i mellemtiden.")
        except Exception as e:
            log.warning("Kunne ikke melde afsendelsesfejl til admin: %s", e)

    def send_text(self, chat_ids: list[int], text: str, svar=None) -> None:
        """Sender og RAPPORTERER resultatet tilbage via svar(ok: bool).
        Tidligere blev resultatet ikke læst — så stod der "Du sendte" på
        skærmen, selv når beskeden aldrig nåede frem (fx uden netværk)."""
        if not (self.loop and self.app):
            if svar:
                svar(False)
            return

        async def send_alle():
            ok = False
            for cid in chat_ids:
                try:
                    await self.app.bot.send_message(chat_id=cid, text=text)
                    ok = True          # mindst én modtager fik beskeden
                    # Virker det igen, skal en ny fejl kunne meldes senere
                    self._send_fejl.discard(cid)
                except Exception as e:
                    log.warning("Kunne ikke sende til %s: %s", cid, e)
                    await self._meld_afsendelsesfejl(cid, e)
            return ok

        fremtid = asyncio.run_coroutine_threadsafe(send_alle(), self.loop)
        if svar:
            # Svaret hentes af en timer-tråd — og svar() må derfor ALDRIG
            # røre Tkinter direkte. Den, der kalder send_text, lægger
            # resultatet i en kø, som UI-tråden tømmer. Se _send_reply.
            #
            # Forsøgene er talte. Uden loftet ville en død event-løkke
            # give en ny timer-tråd hvert halve sekund, resten af dagen —
            # en læk, der først mærkes efter mange timer.
            def tjek(forsoeg: int = 0):
                try:
                    svar(fremtid.result(timeout=0))
                except Exception:
                    if forsoeg >= SEND_SVAR_FORSOEG:
                        log.warning("Fik aldrig svar på afsendelsen — "
                                    "opgiver efter %d sek.",
                                    SEND_SVAR_FORSOEG // 2)
                        svar(False)
                        return
                    threading.Timer(0.5, tjek, (forsoeg + 1,)).start()
            threading.Timer(0.5, tjek).start()

# ----------------------------------------------------------------------------
# UI-lag (hovedtråd, Tkinter fuldskærm)
# ----------------------------------------------------------------------------

REC = "#e63946"            # rød: optagelse i gang / besked kunne ikke sendes
STRIBE_FARVE = "#8c3b2f"   # dæmpet rød stribe i skærmens sider
# Én farve pr. person i "enkelte"-tilstand. Farven går igen tre steder:
# i samtalelisten, i navnehovedet og på personens bobler — så øjet kan se
# HVEM uden at læse. Rækkefølgen på whitelisten bestemmer farven.
# Bevidst valgt uden om svar-farven (cyan), så "mig" og "de andre" aldrig
# kan forveksles, og alle fem ligger over 3:1 mod den mørke bund.
PERSONFARVER = ["#e0a05e", "#8fae7a", "#c98fae", "#d0956b", "#a9a0d8"]
# Statusfirkanten: kan ses tværs over et rum, uden at man læser noget.
#   NY   = fyldt firkant i rød   (5,5:1 mod bunden)
#   LÆST = flueben i grøn        (7,7:1 mod bunden)
# Rød/grøn alene ville være dårligt valgt — omkring hver tolvte mand kan
# ikke skelne dem. Derfor er FORMEN også forskellig (fyldt blok mod
# flueben), og ordene står stadig ved siden af. Farven er en genvej for
# dem, der kan bruge den, aldrig den eneste oplysning.
FARVE_NY = "#ee7566"
FARVE_LAEST = "#8fc47a"
# Farvetemaer — vælges med "tema" i config. Der er **to**, og det er med
# vilje: hver ekstra indstilling er noget mere, der kan stå forkert på en
# maskine, du ikke sidder ved. Luminansforskellen betyder desuden mere end
# farven, og begge temaer ligger langt over kravene.
#
#   varm     (standard) mørk varmgrå bund, råhvid tekst — 13,6:1
#   kontrast næsten-sort bund, neutral næsten-hvid tekst — 16:1, gule navne
#
# Har en bruger brug for noget andet — fx sort på gult, som er
# "clear print"-standarden for svagtseende — så tilføj det DEN DAG, en
# rigtig person ikke kan læse skærmen. Ikke før. Enkelte farver kan i
# øvrigt allerede overskrives med "farver" i config uden et nyt tema.
#
# Farveroller: bg=baggrund, fg=beskedtekst, accent=afsendernavn,
# own=egne svar, day=datooverskrift (dæmpet), top=topbar (dæmpet),
# btn=knapper.
THEMES = {
    # kontrast (standard): opbygget efter anbefalinger for svagtseende.
    #   bg     næsten-sort (#121212) — ren sort mod lys tekst giver mere
    #          halation og virker hårdere; her er kontrasten stadig 16:1
    #   fg     neutral næsten-hvid: lidt under ren hvid mod halation, men
    #          UDEN varm tone — cremede hvidtoner virker "grumsede" på mørk bund
    #   accent GUL — den mest synlige farve på sort; bruges til navne
    #   own    CYAN — tydeligt anderledes end gul, også for farveblinde
    #          (skift til lime "#76ff03" med "farver", hvis det ses bedre)
    #   day    dæmpet blågrå — læsbar, men træder tilbage
    "kontrast": dict(bg="#121212", fg="#f5f5f5", accent="#ffd400",
                     btn="#2a2a2a", own="#4fd8ff", day="#a6a6a6",
                     top="#a6a6a6"),
    # varm: neutral varm palette — mørk varmgrå bund i stedet for kold blå.
    # Den varme råhvid virker harmonisk her (mod en kold/sort bund kan den
    # se "grumset" ud). Kontrast: tekst 13,6:1 · navne 8,9:1 · svar 8,9:1.
    "varm": dict(bg="#252320", fg="#f3eee6", accent="#e0c15e",
                 btn="#312d29", own="#9acbda", day="#d6ccc0",
                 top="#d6ccc0"),
}
# Skriftstørrelser udledes af config "skrift" (standard 28 — store bogstaver
# til ældre øjne; tallet er ikke pixels, se SKRIFT_ANDEL). Afsendernavn og
# knapper skaleres i forhold til den.

def _bland(farve_a: str, farve_b: str, del_b: float) -> str:
    """Blander to hex-farver. Bruges til at udlede boble- og kantfarver
    fra temaet, så nye temaer virker uden ekstra opsætning."""
    a = farve_a.lstrip("#"); b = farve_b.lstrip("#")
    ud = []
    for i in (0, 2, 4):
        va, vb = int(a[i:i+2], 16), int(b[i:i+2], 16)
        ud.append(round(va * (1 - del_b) + vb * del_b))
    return "#%02x%02x%02x" % tuple(ud)


class LivlineUI:
    def __init__(self, config: Config):
        self.config = config
        self.whitelist = Whitelist(config.whitelist_path)
        self.inbox: "queue.Queue[Incoming]" = queue.Queue()
        # Resultater af egne afsendelser, på vej TILBAGE fra bot-tråden.
        # Én vej ind, én vej ud — og begge gennem hovedtråden.
        self._svarkoe: "queue.Queue[tuple]" = queue.Queue()
        self.bot = BotWorker(config, self.whitelist, self.inbox)
        self.last_sender: int | None = None
        # Værn mod en tast, der holdes nede — se SVAR_PAUSE_SEK
        self._sidste_svar: float = 0.0
        self._sidste_svar_tekst: str = ""
        self._svar_spaerret: bool = False
        self._svar_tider: list[float] = []   # se SVAR_MAKS_I_VINDUE
        self.selected: int | None = None      # valgt modtager (enkelte-mode)
        self._rows: list[dict] = []           # hele historikken i hukommelsen
        self._venter: set[int] = set()        # ulæste samtaler
        self._ukvitteret: set[int] = set()    # afsendere, der venter på kvittering
        # Ingen afspiller af nogen art. Video og talebeskeder vises ikke,
        # og maskinen laver aldrig lyd — se _on_message og _show.
        self._historik_fejl: str | None = None  # sat, hvis historikken ikke kunne læses
        self._visfejl_meldt = False         # én melding pr. opstart, se _poll_inbox
        self._img_refs: list = []  # Tkinter kræver at billedreferencer holdes i live

        # Ukendt tema faldt før stille tilbage til "varm". Det er samme
        # fejltype som et stavefejlsramt configfelt: maskinen ser rigtig ud
        # og gør noget andet. Nu siges det højt — i loggen og i
        # /indstillinger, hvor man kigger, når noget undrer en.
        if config.theme not in THEMES:
            log.warning("Ukendt tema %r — bruger 'varm'. Kendte temaer: %s",
                        config.theme, ", ".join(sorted(THEMES)))
        t = dict(THEMES.get(config.theme, THEMES["varm"]))
        t.update({k: v for k, v in config.colors.items() if k in t})  # "farver"
        BG, FG, ACCENT, BTN_BG = t["bg"], t["fg"], t["accent"], t["btn"]
        self._bg, self._accent, self._btn = BG, ACCENT, BTN_BG
        self._top = t.get("top", ACCENT)
        self._fg, self._day = FG, t["day"]

        self.root = tk.Tk()
        self.root.title("Livline")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg=BG)

        # Skrift og billedstørrelse tilpasses bruger og skærm
        fs = self._tilpas_skrift(config.font_size)
        # Normal skriftvægt som i Telegram; "fed": true giver tykkere streger,
        # hvilket kan hjælpe ved svagt syn
        FONT_BODY = (("DejaVu Sans", fs, "bold") if config.bold
                     else ("DejaVu Sans", fs))
        FONT_NAME = ("DejaVu Sans", max(16, int(fs * 0.75)), "bold")
        FONT_BAR = ("DejaVu Sans", max(18, int(fs * 0.85)), "bold")
        # Billeder skaleres efter tekstfeltets FAKTISKE bredde (skærmbredde
        # minus margen i begge sider) — ellers blev de klemt sammen.
        # Billedernes maksimale mål regnes IKKE her — se _billed_maks().
        # Før stod der skærmbredden minus margen, og på en maskine med
        # samtaleliste blev et foto derfor bredere end den plads, det
        # havde: 1840 px i et felt på 1403. Tredje gang samme fejl
        # (boblerne og skrivefeltet var de to første), og derfor spørger
        # alt, der skal fylde noget, nu ét sted.
        global SKRIFT_PX
        try:
            import tkinter.font as tkfont
            SKRIFT_PX = tkfont.Font(root=self.root,
                                    font=FONT_BODY).metrics("linespace")
        except Exception:
            SKRIFT_PX = 0

        just = "center"      # alt indhold centreres (bobler styres af side)

        # Smal farvet stribe i hver side — bryder den store flade
        if config.stripe > 0:
            for side in ("left", "right"):
                tk.Frame(self.root, bg=STRIBE_FARVE,
                         width=config.stripe).pack(side=side, fill="y")

        # Samtaleliste i venstre side — kun ved flere samtaler.
        # Den koster ikke plads, den bruger plads, der stod tom: teksten
        # fylder alligevel kun "tekstbredde" af skærmen, og resten var margen.
        # Listen er endnu ikke trykbar; den viser, hvad F-tasterne gør.
        self.sidebar = None
        self._side_sig = None
        if config.mode == "enkelte":
            self.sidebar = tk.Frame(self.root, bg=BG,
                                    padx=int(config.margin * 0.4),
                                    pady=int(config.margin * 0.4))
            self.sidebar.pack(side="left", fill="y")

        # Topbar: modtagervalg (enkelte) eller fællestråd-info — dæmpet farve,
        # så den ikke konkurrerer med afsendernavnene om opmærksomheden
        # Hovedet er en RAMME med to etiketter: teksten og statustegnet.
        # Grunden: Tk kan ikke farve dele af en tekst, og tegnet skal have
        # sin egen betydning-farve (rød/grøn), mens navnet har personens.
        # Tegnet står EFTER teksten — samme opbygning som i samtalelisten,
        # så øjet finder det samme sted begge steder.
        self.topbar = tk.Frame(self.root, bg=BG, pady=12)
        self.topbar.pack(fill="x")
        # Tekst og tegn ligger i en INDRE ramme, som centreres samlet.
        # Uden den fik teksten hele bredden og blev centreret for sig, mens
        # tegnet endte ude i højre side — altså ikke "lige efter teksten",
        # som det er i samtalelisten. De to skal følges ad.
        self._top_midte = tk.Frame(self.topbar, bg=BG)
        self._top_midte.pack(expand=True)
        self._top_tekst = tk.Label(self._top_midte, bg=BG, fg=self._top,
                                   font=FONT_BAR)
        self._top_tekst.pack(side="left")
        self._top_tegn = tk.Label(self._top_midte, bg=BG, fg=self._top,
                                  font=FONT_BAR, padx=12)
        self._top_tegn.pack(side="left")

        # NETLINJEN. Kun på skærmen, når der er noget galt.
        #
        # Er nettet væk, ser skærmen præcis ud som en skærm, hvor familien
        # ikke har skrevet. Den ældre kan ikke se forskel, og familien kan
        # heller ikke: deres beskeder ser afsendte ud i Telegram.
        #
        # Linjen står FOR SIG, ikke i stedet for hovedet. "Ny besked" er
        # en oplysning, der ikke må forsvinde, fordi der kommer en anden.
        #
        # Den beder ham ikke om at gøre noget. Han kan ikke rette det, og
        # en linje, der antyder, at han burde, er værre end ingen linje.
        self._netlinje = tk.Label(
            self.root, bg=BG, fg=FARVE_NY, font=FONT_BAR, pady=6,
            text="⚠️  Ingen forbindelse — beskeder kommer frem, "
                 "når den er tilbage")
        self._net_vist = False

        # VIGTIGT: bundbaren pakkes FØR beskedfeltet, så knapperne altid har
        # reserveret plads. Ellers kan beskedfeltet (expand=True) skubbe dem
        # ud af skærmen ved stor skrift — fejl rettet i 1.3.
        # tast -> svartekst (tasterne kommer fra config "taster")
        # zip() stopper ved den korteste liste UDEN at sige noget. Er der
        # flere svar end taster, ville det sidste svar forsvinde lydløst:
        # teksten står på tastaturdækket, og tasten gør ingenting.
        # Config.load fylder tasterne op, så det bør ikke kunne ske — men
        # "bør ikke kunne ske" er ikke det samme som "siger til, hvis det gør".
        if len(config.keys) != len(config.replies):
            log.warning("%d taster til %d svar — de sidste svar kan ikke "
                        "sendes. Ret \"taster\" i config.",
                        len(config.keys), len(config.replies))
        self.replies = dict(zip(config.keys, config.replies))
        self._knapper: list = []
        # "vis_knapper": false → ingen knaprad på skærmen; tasterne virker
        # stadig (teksterne står som mærkater over tasterne på maskinen)
        if self.replies and config.show_buttons:
            # Hjælpelinjen pakkes FØR knapraden, så den lander nederst —
            # samme sted som i skrivefelt-tilstand. Den siger, hvad Enter
            # gør lige nu, og i knap-tilstand betyder Enter kun én ting:
            # "jeg har set det".
            self._hjaelp = tk.Label(self.root, text="", bg=BG, fg=self._top,
                                    font=FONT_BAR, anchor="center")
            self._hjaelp.pack(side="bottom", fill="x", pady=(0, 10))
            self.botbar = tk.Frame(self.root, bg=BG)
            self.botbar.pack(side="bottom", fill="x", padx=config.margin,
                             pady=(6, 18))
            for k, label in (self.replies.items() if config.show_buttons else []):
                # ved "æ/ø" vises kun det første tegn på knappen
                # KUN TEKSTEN. Før stod tasten med på knappen — "Tak  [Q]".
                # Bogstavet er skrevet fysisk over tasten på maskinen, så på
                # skærmen var det en gentagelse, der tog plads fra ordene.
                # Skærmen skal vise BESKEDEN; tastaturet skal vise tasten.
                vis = label
                # wraplength sættes rigtigt af _juster_knapper, når vinduet
                # er tegnet. Her sættes blot noget brugbart, så den første
                # optegning ikke står forkert.
                knap = tk.Button(self.botbar, text=vis, font=FONT_BAR,
                                 bg=BTN_BG, fg=FG, activebackground=ACCENT,
                                 pady=16, wraplength=400,
                                 command=lambda txt=label: self._send_reply(txt))
                knap.pack(side="left", expand=True, fill="x", padx=12)
                self._knapper.append(knap)

        # Boblefarver udledes af temaet, så alle temaer virker uden opsætning:
        # modtaget = panelfarven, egne = panelfarven tonet mod svar-farven.
        # De beregnes HER — før skrivefeltet — fordi feltet låner præcis de
        # samme værdier. Ét sted at rette, og de to kan ikke drive fra
        # hinanden ved en senere ændring.
        self._boble_ind = t["btn"]
        self._kant_ind = _bland(t["btn"], t["fg"], 0.30)
        self._boble_ud = _bland(t["bg"], t["own"], 0.22)
        self._kant_ud = t["own"]

        # Skrivefelt (over knapperne): brugeren kan skrive frit og trykke Enter
        self.entry = None
        if config.text_input:
            # SKRIVEFELTET SKAL STÅ I SAMME SPALTE SOM BESKEDERNE.
            #
            # Set i drift: feltet begyndte 217 px længere til venstre end
            # nogen beskedboble. Når man skrev, startede teksten altså uden
            # for den spalte, samtalen ellers holder sig i — og det så ud,
            # som om den løb ud over kanten.
            #
            # Grunden var, at feltet blev centreret med en fast margen i
            # hele vinduets bredde, mens beskederne centreres inde i
            # tekstfeltet, som starter til HØJRE for samtalelisten. To
            # forskellige regler for det samme.
            #
            # Nu er der én regel: bredden følger "tekstbredde", præcis som
            # boblerne, og feltet lægges midt i tekstfeltet. Fordi
            # samtalelisten kan skifte bredde (navne kommer og går), måles
            # der efter opsætningen — se _juster_feltbredde.
            wrap = tk.Frame(self.root, bg=BG)
            wrap.pack(side="bottom", fill="x", padx=config.margin, pady=(0, 18))
            self._felt_wrap = wrap
            # Hjælpelinjen står ALTID under feltet — fast tekst er mere robust
            # end en pladsholder inde i feltet, som skal ryddes og genskabes
            # ved hvert tastetryk (og som kan nå at blive sendt ved et uheld).
            # ⏎ (U+23CE) findes i DejaVu Sans — kontrolleret. Symbolet står
            # samme sted som på tastaturets Enter-tast, så de to hører sammen.
            hjaelp = "Skriv her og tryk ⏎ Enter"
            self._hjaelp = tk.Label(wrap, text=hjaelp, bg=BG, fg=self._top,
                                    font=("DejaVu Sans",
                                          max(13, int(fs * 0.55))),
                                    anchor="w", justify="left")
            self._hjaelp.pack(side="bottom", fill="x", pady=(6, 0))
            felt = tk.Frame(wrap, bg=BG)
            felt.pack(fill="x")
            # DER ER INGEN SEND-KNAP. Den fandtes før og fulgte
            # "vis_knapper", men er fjernet af to grunde:
            #
            #   1. Uden touch er den overflødig. Hjælpelinjen under feltet
            #      siger allerede, hvad Enter gør — og knappen tog 13 % af
            #      skærmbredden fra feltet (målt: 46 % med, 59 % uden).
            #   2. MED touch er Send heller ikke det, man vil trykke på.
            #      Det er NAVNET på den, man skriver til. Samtalelisten er
            #      den rigtige touch-flade; en Send-knap ville bare stå i
            #      vejen for den.
            #
            # Sidegevinst: "vis_knapper" betyder nu kun ÉN ting — om
            # svarknapperne vises i knap-tilstand. Før betød den to
            # forskellige ting afhængigt af tilstand, og den slags
            # dobbeltbetydning giver før eller siden en maskine, der
            # opfører sig anderledes, end man tror.
            # To linjer højt i tom tilstand — nok til at feltet ligner et sted,
            # man kan skrive, uden at tage plads fra samtalen. Det vokser til
            # seks linjer med teksten, som ombrydes i stedet for at rulle ud
            # til venstre, sådan som et Entry-felt gør.
            # width=1: et Tk-tekstfelt beder ellers om plads til 80 tegn, og
            # ved stor skrift blev det bredere end skærmen — så røg Send-
            # knappen ud over kanten. Med width=1 beder feltet om næsten
            # ingenting og fylder i stedet den plads, pack() giver det.
            # (Samme fælde som knapraden i 1.3.)
            # Feltet ser ud som brugerens EGEN boble: samme fyld, samme kant,
            # samme luft indeni. Så er skrivefeltet den tomme boble, teksten
            # er på vej ind i — og ved Enter glider den bare op i samtalen.
            # En rød kant blev prøvet først og forkastet: en farve, der ikke
            # findes andre steder på skærmen, tiltrækker sig mere opmærksomhed,
            # end funktionen fortjener. Her tilføjes hverken ny farve eller ny
            # form; feltet låner et sprog, brugeren allerede har lært.
            self.entry = tk.Text(felt, font=FONT_BODY,
                                 bg=self._boble_ud, fg=FG,
                                 insertbackground=FG, relief="flat", wrap="word",
                                 width=1, height=FELT_MIN,
                                 padx=18, pady=12,        # som boblens padding
                                 spacing1=2, spacing3=2,
                                 highlightthickness=2,    # som en hvilende boble
                                 highlightbackground=self._kant_ud,
                                 highlightcolor=self._kant_ud)
            self.entry.pack(side="left", expand=True, fill="x")
            # Enter sender. "break" forhindrer, at Tk OGSÅ indsætter et
            # linjeskift i feltet, efter beskeden er sendt.
            self.entry.bind("<Return>", lambda e: (self._send_typed(), "break")[1])
            self.entry.bind("<KP_Enter>",
                            lambda e: (self._send_typed(), "break")[1])
            self.entry.bind("<Escape>", lambda e: self._ryd_kladde())
            self.entry.bind("<KeyRelease>", self._kladde_aendret)
            # Pilene ruller i samtalen — også når markøren står i feltet.
            # Feltet er kun to-seks linjer, så markørflytning betyder lidt; at
            # pilene gør det SAMME på alle maskiner betyder meget.
            self.entry.bind("<Up>", lambda e: (self._scroll(-1), "break")[1])
            self.entry.bind("<Down>", lambda e: (self._scroll(1), "break")[1])

        # Beskedfeltet fylder resten af skærmen (pakkes sidst, se ovenfor)
        self.text = tk.Text(self.root, bg=BG, fg=FG, font=FONT_BODY, wrap="word",
                            state="disabled", relief="flat",
                            # NB: pady på en widget skal være ÉT tal —
                            # tupler virker kun i pack()/grid(). (En tuple
                            # her gav 'bad screen distance' og crash i 3.3-3.6.)
                            padx=config.margin, pady=20,
                            spacing1=2, spacing2=4, spacing3=int(fs * 0.45),
                            cursor="none")
        # Indrykning så TEKSTEN højst fylder config.text_width af skærmen.
        # Billeder får mærket "billede" uden indrykning og bevarer fuld bredde.
        # Indrykningen sættes rigtigt af _juster_bredder, så snart vinduet
        # er tegnet og sidelistens bredde er kendt. Her sættes den blot til
        # noget brugbart, så det første, der tegnes, ikke står forkert.
        # (Før blev den regnet ud af skærmbredden HER og overskrevet et
        #  øjeblik efter — to beregninger af samme tal, hvor den ene altid
        #  tabte. Det er dagens gennemgående fejltype.)
        ind = self._spalte()[0]
        self.text.tag_configure("std", justify=just, lmargin1=ind,
                                lmargin2=ind, rmargin=ind)
        self.text.tag_configure("name", font=FONT_NAME, foreground=ACCENT,
                                justify=just, spacing1=int(fs * 0.9),
                                spacing3=int(fs * 0.1), lmargin1=ind,
                                lmargin2=ind, rmargin=ind)
        self.text.tag_configure("own", foreground=t["own"], justify=just,
                                lmargin1=ind, lmargin2=ind, rmargin=ind)
        self.text.tag_configure("billede", justify=just)
        self.text.tag_configure("tom", justify="center", foreground=t["day"],
                                spacing1=int(fs * 2))
        # Boble-placering: modtagne til venstre, egne til højre — begge
        # inden for en midterspalte, så samtalen ikke spredes ud til kanterne
        self.text.tag_configure("venstre", justify="left",
                                lmargin1=ind, lmargin2=ind, rmargin=ind)
        self.text.tag_configure("hoejre", justify="right",
                                lmargin1=ind, lmargin2=ind, rmargin=ind)

        self._font_body, self._font_name = FONT_BODY, FONT_NAME
        self._font_tid = ("DejaVu Sans", max(12, int(fs * 0.55)))
        # (boblernes bredde regnes af _spalte(), som måler på tekstfeltet —
        #  ikke på skærmen. Se forklaringen dér.)
        self.text.pack(fill="both", expand=True)

        # Tastebindinger
        for i, key in enumerate(FKEYS):
            self.root.bind(f"<{key}>", lambda e, idx=i: self._select_fkey(idx))
        # Genvejstasterne sender faste svar. I "tastatur"-tilstand findes der
        # ingen faste svar, så bindingerne oprettes slet ikke — og der kan
        # derfor ikke opstå konflikt med skrivefeltet.
        # "æ/ø" binder begge tegn til samme svar; både lille og stort
        # bogstav bindes, så Caps Lock ikke kan spænde ben.
        for k in self.replies:
            for tegn in k.split("/"):
                tegn = tegn.strip()
                for variant in {tegn.lower(), tegn.upper()}:
                    keysym = KEYSYM.get(variant, variant)
                    try:
                        # "<Key-1>", IKKE "<1>". I Tk betyder <1> MUSEKNAP 1,
                        # <2> midterklik og <3> højreklik. Med den gamle form
                        # virkede taltasterne aldrig — og et klik hvor som
                        # helst på skærmen sendte en besked i stedet.
                        #
                        # Fejlen var usynlig, så længe der stod bogstaver i
                        # "taster" (a, c, n, l er ikke tvetydige), og netop
                        # derfor overlevede den: standardopsætningen 1/2/3
                        # blev aldrig prøvet på en rigtig maskine, før
                        # denne her blev bygget fra bunden.
                        self.root.bind(
                            f"<Key-{keysym}>",
                            lambda e, kk=k: self._send_reply(self.replies[kk]))
                    except tk.TclError:
                        log.warning("Ukendt genvejstast i config: %r", tegn)
        # ENTER BETYDER DET SAMME I ALLE OPSÆTNINGER: "jeg har set det".
        #
        # Før hang Enter kun på skrivefeltet. I knap-tilstand findes feltet
        # ikke, så tasten gjorde ingenting — og den eneste måde at kvittere
        # på var at sende et svar. Dermed blev "jeg har set det" og "jeg
        # svarer dig" til det samme, og for den, der sidder med telefonen,
        # er de to ting ikke det samme.
        #
        # Skrivefeltet har sin egen binding, som både sender og kvitterer;
        # den her gælder kun, når der ikke er noget felt.
        if self.entry is None:
            self.root.bind("<Return>",
                           lambda e: self._kvitter(self.selected
                                                   or self.last_sender))
            self.root.bind("<KP_Enter>",
                           lambda e: self._kvitter(self.selected
                                                   or self.last_sender))
        # Pil op/ned scroller i beskederne (erstatter xbindkeys-hack fra 2.1.6)
        self.root.bind("<Up>", lambda e: self._scroll(-1))
        self.root.bind("<Down>", lambda e: self._scroll(1))
        if self.entry is not None:
            self.entry.focus_set()   # klar til at skrive med det samme
        # Registrér al tastaturaktivitet til idle-nulstilling
        self._last_key = time.monotonic()
        self.root.bind_all("<Key>", self._note_activity, add="+")
        # Nødudgang til service — bevidst svær at ramme ved et uheld.
        # (Escape alene lukkede appen indtil 2.16.)
        self.root.bind("<Control-Alt-Escape>", lambda e: self.root.destroy())

        # NATTETÆPPET: en sort flade, der dækker alt. Den tegnes af appen
        # selv og ikke af skrivebordet — vi har brugt dagen på at lære, at
        # skrivebordets indstillinger kan blive overskrevet, mens en flade,
        # programmet selv tegner, ikke kan tages fra os.
        self._nat_taeppe = tk.Frame(self.root, bg="#000000")
        self._nat_taeppe.place(x=0, y=0, relwidth=1, relheight=1)
        self._nat_taeppe.lower()
        self._nat_nu = None

        self._refresh_topbar()
        # Spalten skal rettes til i BEGGE betjeningsformer — boblerne findes
        # også i knap-tilstand, hvor der ikke er noget skrivefelt.
        self.root.after_idle(self._juster_bredder)
        self.root.after(400, self._juster_bredder)

    def run(self) -> None:
        self._load_history()
        # Kunne historikken ikke læses, må skærmen IKKE bare se tom ud.
        # En tom skærm læses som "ingen har skrevet" — og det er en helt
        # anden besked end "jeg kan ikke komme til det, der er skrevet".
        if self._historik_fejl:
            self._insert("⚠️  Tidligere beskeder kunne ikke læses. "
                         "Nye beskeder virker.\n", tag="name")
        # Er skærmen tom, ville den ligne en slukket maskine — vis en
        # dæmpet linje, der forsvinder ved første besked
        elif self.text.index("end-1c") == "1.0":
            self._insert("Venter på beskeder fra familien\n", tag="tom")
            self._tom_linje = True
        self.bot.start()
        self._poll_inbox()
        self._idle_check()
        self._vindue_vagt()
        self._nat_vagt()
        if self.entry is not None:
            self._autosend_check()
        self.root.mainloop()

    # -- historik (overlever den daglige nedlukning) ---------------------------

    @property
    def _history_path(self) -> Path:
        return self.config.whitelist_path.parent / "historik.json"

    def _load_history(self) -> None:
        """Viser gemte beskeder igen ved opstart, så skærmen ikke er tom
        om morgenen efter den planlagte nedlukning kl. 22.

        Rækkerne gemmes også i hukommelsen (self._rows), så én samtale kan
        tegnes igen, når brugeren skifter modtager i "enkelte"-tilstand."""
        try:
            rows = json.loads(self._history_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return                      # frisk maskine — helt normalt
        except Exception as e:
            # EN TOM SKÆRM LIGNER EN UBRUGT MASKINE.
            # Her stod bare "return". Var historikken beskadiget, startede
            # maskinen med "Venter på beskeder fra familien" — som om
            # ingen havde skrevet. Ingen kunne se, at måneders samtale var
            # utilgængelig.
            log.warning("Kunne ikke læse historikken: %s", e)
            self._historik_fejl = str(e)
            return
        rows = rows[-HISTORY_MAX:]
        self._rows = list(rows)

        # HVEM VENTER STADIG PÅ EN KVITTERING?
        #
        # Her lå en fejl, der ramte HVER NAT. Maskinen genstarter kl. 3.
        # Skrev familien kl. 23.30, og han sov, blev beskeden genskabt på
        # skærmen — men _ukvitteret blev ikke genskabt. Om morgenen stod
        # der "Læst 23.30" med grønt flueben, familien havde aldrig fået
        # en kvittering, og trykkede han Enter, skete der ingenting.
        #
        # Reglen her er den samme som i _kvitter: en indgående besked
        # venter, indtil der kommer et eget svar. I fællestråd rydder ét
        # svar hele tråden; i enkelte kun den ene samtale.
        self._ukvitteret = set()
        for r in rows:
            try:
                cid = int(r["chat_id"])
            except (KeyError, ValueError, TypeError):
                continue
            if r.get("egen"):
                if self.config.mode == "faellestraad":
                    self._ukvitteret.clear()
                else:
                    self._ukvitteret.discard(cid)
            else:
                self._ukvitteret.add(cid)
        if self._ukvitteret:
            log.info("Efter opstart venter %d besked(er) stadig på kvittering",
                     len(self._ukvitteret))
        if self.config.mode == "enkelte":
            # Vis kun den seneste samtale — resten hentes frem med F-tasterne
            for r in reversed(rows):
                try:
                    self.selected = int(r["chat_id"])
                    break
                except (KeyError, ValueError, TypeError):
                    continue
            rows = [r for r in rows
                    if str(r.get("chat_id")) == str(self.selected)]
        # Kun de nyeste billeder genskabes — ældre vises som "(billede)".
        # 100 fotos i fuld størrelse ville gøre opstarten tung.
        billed_graense = len(rows) - REPLAY_IMAGES
        for nr, r in enumerate(rows):
            if r.get("type") == "photo" and nr < billed_graense:
                r = dict(r, fil=None)
            if r.get("egen"):          # brugerens eget svar — højrestillet
                try:
                    tid = datetime.fromisoformat(r["tid"])
                    self._boble(r.get("tekst", ""),
                                f"kl. {tid.strftime('%H.%M')} "
                                f"{self._day_label(tid).lower()}",
                                None, egen=True)
                except Exception as e:
                    log.warning("Sprang eget svar over i historikken: %s", e)
                continue
            try:
                m = Incoming(
                    sender_name=r["navn"], chat_id=int(r["chat_id"]),
                    kind=r["type"], text=r.get("tekst", ""),
                    file_path=Path(r["fil"]) if r.get("fil") else None,
                    received=datetime.fromisoformat(r["tid"]))
                self._show(m, replay=True)
            except Exception as e:
                log.warning("Sprang beskadiget historik-post over: %s", e)

    # (Historikken skrives nu i bot-tråden ved modtagelsen — se gem_i_historik)

    def _rul_til_bund(self) -> None:
        """Ruller helt til bunds i indholdet, EFTER at boblen er tegnet.
        see("end") sikrer kun, at sidste LINJE er synlig — ikke bunden af en
        indlejret boble, så klokkeslættet kunne havne under skærmkanten.
        yview_moveto(1.0) ruller derimod til indholdets ende."""
        def bund():
            self.text.update_idletasks()
            self.text.yview_moveto(1.0)
        self.root.after_idle(bund)
        self.root.after(150, bund)      # igen når billeder/bobler er målt

    # -- scroll og inaktivitet -------------------------------------------------

    def _tilpas_skrift(self, oensket: int) -> int:
        """Retter skriftstørrelsen, så teksten fylder den samme andel af
        skærmhøjden på alle maskiner.

        Måler hvad ét punkt FAKTISK bliver til på netop denne skærm, og
        skalerer tallet derefter. Det er nødvendigt, fordi hverken skærmens
        DPI-påstand eller skrivebordets egen forstørrelse kan forudsiges:
        set i drift meldte en 14" 3072x1728-skærm sig som 813x457 mm, og
        oveni lå en 200 %-skalering fra skrivebordet.

        Grænserne sidder på RESULTATET, ikke på justeringen: skriften skal
        ende mellem 8 punkter og en tolvtedel af skærmhøjden. En grænse på
        selve faktoren så fornuftig ud, men skar justeringen af på en høj
        skærm med lav skalering — fanget af prøven på 1366x1728.

        Går målingen galt, beholdes brugerens tal uændret: en skæv skrift er
        et skønhedsproblem, en app der ikke starter er et driftsproblem."""
        try:
            import tkinter.font as tkfont
            hoejde = self.root.winfo_screenheight()
            maal = hoejde * SKRIFT_ANDEL * oensket
            # root=self.root: uden den måler Tk i programmets FØRSTE vindue.
            # Det er altid det rigtige i drift (der er kun ét), men gør
            # målingen afhængig af noget, den ikke burde kende — og i
            # prøvekørslen gav det en skrift på 130 px, fordi et andet
            # vindue havde en ekstrem skalering.
            faktisk = tkfont.Font(root=self.root, family="DejaVu Sans",
                                  size=oensket).metrics("linespace")
            if faktisk <= 0:
                return oensket
            rettet = min(max(8, round(oensket * maal / faktisk)), hoejde // 12)
            log.info("Skærm %dx%d px (%dx%d mm) — skrift %d gav %d px, "
                     "mål %d px, bruger %d",
                     self.root.winfo_screenwidth(),
                     self.root.winfo_screenheight(),
                     self.root.winfo_screenmmwidth(),
                     self.root.winfo_screenmmheight(),
                     oensket, faktisk, round(maal), rettet)
            return rettet
        except Exception as e:
            log.warning("Kunne ikke tilpasse skriften (%s) — bruger %d som den er",
                        e, oensket)
            return oensket

    def _vindue_vagt(self, forsoeg: int = 0) -> None:
        """Holder Livline-vinduet øverst på skærmen.

        Historien bag: v4.16 tjekkede, om vinduet var "synligt", og hentede
        det kun frem, hvis ikke. Det viste sig at være en for svag prøve —
        winfo_viewable() fortæller, at vinduet er TEGNET, ikke at det er
        ØVERST. I drift meldte vagten derfor kun én gang ved opstart, mens
        skærmen resten af dagen viste skrivebordet.

        Nu måles der ikke. Vinduet sættes ØVERST igen med faste mellemrum,
        uanset hvad Tk mener om sagen. På en maskine, der kun kører ét
        program, er det både det enkleste og det mest robuste: der er ikke
        noget andet vindue, der har ret til at ligge foran.

        Hvert 5. sekund det første minut (opstarten er, hvor det går galt),
        derefter hvert halve minut."""
        # Her stod en pause, mens en video havde skærmen. Video vises ikke
        # længere, og lyd åbner intet vindue — så vagten skal ALDRIG holde
        # pause. Et vindue foran Livline er nu altid en fejl.
        try:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.attributes("-fullscreen", True)
            self.root.lift()
            if self.entry is not None and self.root.focus_get() is None:
                self.entry.focus_set()
            self._skjul_markoer()
        except tk.TclError:
            return          # vinduet er lukket — vagten stopper med det
        naeste = 5_000 if forsoeg < VINDUE_VAGT_TIDLIGE else 30_000
        self.root.after(naeste, lambda: self._vindue_vagt(forsoeg + 1))

    def _skjul_markoer(self, w=None) -> None:
        """Skjuler musemarkøren på ALLE flader.

        cursor="none" stod kun på beskedfeltet. Overalt andet — vinduet,
        skrivefeltet, knapperne, samtalelisten — lå pilen synlig. På en
        maskine uden mus er det bare en pil, der flyder rundt på skærmen,
        og om natten lyser den.

        Der gås igennem hver gang i stedet for at sætte det én gang ved
        opbygningen: boblerne laves løbende, efterhånden som beskederne
        kommer ind, og en engangsindstilling ville ikke nå dem. Samme
        princip som -topmost — sæt tilstanden, mål den ikke.

        GENNEMGANGEN ER IKKE REKURSIV, og det er med vilje. Første udgave
        skrev "w = w or self.root" for at kunne kaldes uden argument. Var
        en widget så "falsk" i Pythons forstand, blev den lavet om til
        roden, og gennemgangen løb i ring — 75 prøver faldt med
        RecursionError. En bunke og et besøgt-sæt kan ikke løbe løbsk,
        uanset hvordan Tk finder på at opføre sig."""
        start = self.root if w is None else w
        bunke = [start]
        besoegt = set()
        while bunke:
            n = bunke.pop()
            navn = str(n)
            if navn in besoegt:
                continue
            besoegt.add(navn)
            try:
                n.configure(cursor="none")
            except tk.TclError:
                pass        # ikke alle widgets har en markør at skjule
            try:
                bunke.extend(n.winfo_children())
            except tk.TclError:
                pass

    def _er_nat(self, naar: datetime | None = None) -> bool:
        """Er klokken inden for nattetimerne fra config?

        Perioden går hen over midnat, så den kan ikke skrives som ét
        interval — deraf 'eller' i stedet for 'og'."""
        start, slut = self.config.nat
        t = (naar or datetime.now()).hour
        return t >= start or t < slut

    def _nat_vagt(self) -> None:
        """Slukker og tænder skærmen efter klokken.

        MASKINEN SLUKKER IKKE LÆNGERE. Den gjorde det før kl. 22 og skulle
        vækkes af urets alarm kl. 07.59 — men prøvet på hardware kunne
        maskinen slet ikke vækkes af uret, og så lå den slukket hele dagen.
        Vi kan ikke regne med, at en genbrugt maskine kan vågne.

        En maskine, der KØRER, kan derimod genstarte sig selv. Derfor:
        skærmen bliver sort om natten, maskinen bliver ved, og
        genstarten kl. 03 klarer den friske start, nedlukningen skulle give.

        Beskeder modtages hele natten. De står der bare om morgenen —
        skærmen lyser ikke op kl. 23.30, fordi nogen skriver."""
        nat = self._er_nat()
        foer = getattr(self, "_nat_nu", None)
        try:
            # SKÆRMEN SÆTTES HVER RUNDE — der spørges ikke, om den allerede
            # står rigtigt. Samme regel som vinduesvagten, og af samme
            # grund: den farlige fejl er en skærm, der bliver sort om
            # morgenen, for så ligner maskinen en, der er død, og familien
            # ringer ikke — de tror bare, den er gået i stykker. Fejler et
            # kald, retter næste runde det et halvt minut senere.
            #
            # Om natten vækkes skærmen af et tastetryk og slukker igen efter
            # NAT_VAEK_SEK uden aktivitet.
            vaagen = (not nat) or (time.monotonic() - self._last_key
                                   < NAT_VAEK_SEK)
            self._panel(vaagen)
            self._baglys(None if vaagen else 0)

            if nat != foer:
                self._nat_nu = nat
                if nat:
                    self._nat_taeppe.lift()
                else:
                    self._nat_taeppe.lower()
                log.info("Nattilstand: %s", "skærmen slukket" if nat else "skærmen tændt")
                # FØR blev _nat_nu sat ovenfor og derefter sammenlignet med
                # None — den prøve var altid sand, så en genstart midt på
                # dagen sendte en ☀️-besked. Nu sammenlignes der med den
                # FORRIGE værdi, og første runde er tavs, som den skal være.
                if not nat and foer is not None:
                    # Morgenens livstegn. Det lå før i startbeskeden, men
                    # maskinen starter ikke længere om morgenen — den har
                    # kørt hele natten.
                    self.bot.send_admin("☀️ " + self.bot._status_text())
        except tk.TclError:
            return
        self.root.after(NAT_TJEK_SEK * 1000, self._nat_vagt)

    def _panel(self, taendt: bool) -> None:
        """Tænder eller SLUKKER selve skærmpanelet.

        Målt på hardware, i et mørkt rum: baggrundslys 0 slukker ikke
        lysdioderne — panelet lyser stadig svagt blåt, og det kan ses fra
        en seng. bl_power=4 blev taget imod af driveren og derefter
        ignoreret. Det eneste, der gav en HELT sort skærm, var at bede
        GNOME slukke den. På Wayland ejer GNOME skærmen; ingen andre kan.

        Låseskærmen skal være slået fra (install.sh gør det), ellers ville
        der stå et adgangskodebillede foran appen, når skærmen vækkes — og
        det er værre end alt det, vi prøver at undgå.

        Der gemmes ikke en tilstand her med vilje. Et tastetryk får GNOME
        til at tænde skærmen bag om ryggen på os, og en husket tilstand
        ville så være forkert uden at nogen opdagede det."""
        try:
            subprocess.run(
                ["gdbus", "call", "--session",
                 "--dest", "org.gnome.ScreenSaver",
                 "--object-path", "/org/gnome/ScreenSaver",
                 "--method", "org.gnome.ScreenSaver.SetActive",
                 "false" if taendt else "true"],
                check=True, capture_output=True, timeout=5)
            self._panel_fejl = 0
        except Exception as e:
            # Kun første fejl siges højt. Ellers ville en maskine uden
            # GNOME-forbindelse fylde loggen med 2.880 linjer i døgnet, og
            # så ville ingen kunne finde de vigtige.
            if not getattr(self, "_panel_fejl", 0):
                log.warning("Kunne ikke %s skærmen: %s",
                            "tænde" if taendt else "slukke", e)
            self._panel_fejl = getattr(self, "_panel_fejl", 0) + 1

    def _baglys(self, vaerdi: int | None) -> None:
        """Skruer baggrundslyset ned om natten og op igen om morgenen.

        En sort flade lyser stadig svagt. Står maskinen i et soveværelse,
        er forskellen mellem 'sort skærm' og 'slukket lys' til at mærke.
        FUNKTIONEN VIRKEDE IKKE I HALVANDEN MÅNED, og den fortalte det
        ikke. /sys/class/backlight/*/brightness ejes af root, appen kører
        som kiosk-brugeren, og skrivningen fejlede hver gang — men fejlen
        blev slugt af en log.debug, som ingen læser. Skærmen stod på 313 af
        1023 hele natten, mens alt så rigtigt ud.

        install.sh giver nu gruppen "video" skriveadgang. Fejler det
        alligevel, siges det højt én gang, så det kan ses i loggen og
        rettes — i stedet for at forsvinde."""
        try:
            import glob
            mapper = glob.glob("/sys/class/backlight/*/")
            skrevet = 0
            for sti in mapper:
                maks = Path(sti + "max_brightness")
                akt = Path(sti + "brightness")
                if not maks.exists():
                    continue
                m = int(maks.read_text().strip())
                # Om dagen: den andel af maksimum, config beder om.
                # Om natten (vaerdi=0): helt slukket.
                dag = max(1, round(m * self.config.lysstyrke / 100))
                akt.write_text(str(dag if vaerdi is None else vaerdi))
                skrevet += 1
            if mapper and not skrevet:
                raise OSError("ingen af panelerne kunne skrives")
            self._lys_fejl = 0
        except Exception as e:
            if not getattr(self, "_lys_fejl", 0):
                log.warning("Kunne ikke ændre baggrundslyset (%s). "
                            "Mangler kiosk-brugeren skriveadgang til "
                            "/sys/class/backlight/*/brightness?", e)
            self._lys_fejl = getattr(self, "_lys_fejl", 0) + 1

    def _note_activity(self, _event=None) -> None:
        self._last_key = time.monotonic()

    def _scroll(self, retning: int) -> None:
        """Ruller en fjerdedel af SKÆRMEN — ikke en andel af hele samtalen.

        Tk's egen linjerulning er ubrugelig her, fordi én "linje" kan være
        en hel beskedboble eller et billede; ét tastetryk kunne hoppe langt.

        Men den første løsning var lige så skæv: den rullede 8 % af HELE
        indholdet. Det er en meningsløs enhed — med hundrede beskeder er 8 %
        et spring på flere skærmfulde, med fem beskeder er det ingenting.
        Set i drift: den løb alt for hurtigt.

        En fjerdedel af det, brugeren faktisk kan se, er derimod det samme
        hver gang. Tre tryk giver knap en skærmfuld, og der bliver altid et
        stykke tilbage af det, hun lige læste — så hun kan finde sig selv
        igen."""
        top, bund = self.text.yview()
        synlig = max(0.02, bund - top)      # hvor stor en del af alt, der ses
        andel = synlig * RUL_ANDEL * (1 if retning > 0 else -1)
        ny = min(1.0, max(0.0, top + andel))
        self.text.yview_moveto(ny)

    def _idle_check(self) -> None:
        """Som gammel auto-scroll: efter 5 min uden tastetryk rulles til
        nyeste besked, hvis brugeren har scrollet op og glemt det."""
        idle = time.monotonic() - self._last_key
        if idle > IDLE_RESET_SEC and self.text.yview()[1] < 1.0:
            self.text.yview_moveto(1.0)
        self.root.after(30_000, self._idle_check)

    # -- modtagere -------------------------------------------------------------

    def _recipients(self) -> list[int]:
        if self.config.mode == "faellestraad":
            return self.whitelist.ids()
        target = self.selected or self.last_sender
        return [target] if target else []

    def _select_fkey(self, idx: int) -> None:
        if self.config.mode != "enkelte":
            return  # F-taster bruges ikke i fællestråd
        ids = self.whitelist.ids()
        if idx >= len(ids):
            return
        if ids[idx] != self.selected:
            self.selected = ids[idx]
            self._venter.discard(self.selected)
            self._tegn_samtale()
        # Kvitteringen sendes ALTID ved et tastetryk — også når samtalen
        # allerede stod på skærmen, fordi den sprang derhen af sig selv.
        # Trykket er brugerens handling, og det er den, der betyder "set".
        # (Fanget af prøven: uden dette gav F2 ingen kvittering, hvis
        # skærmen i forvejen viste den samtale.)
        self._kvitter(ids[idx])

    def _refresh_topbar(self) -> None:
        # NB: kun FARVERNE er fredet under et blink (se _flash) — teksten skal
        # altid kunne opdateres. Før returnerede den her tidligt, og så kunne
        # en ny markering blive væk i op mod halvandet sekund. Fanget af
        # prøven "skærmen skifter IKKE, mens der står uafsendt tekst".
        if self.config.mode == "faellestraad":
            # HOVEDET SKAL BÆRE EN OPLYSNING, ikke en overskrift. Før stod
            # der kun "Fællestråd — alle ser dine svar" hele dagen: sandt,
            # men uden nyt indhold. Nu står det samme som i den anden
            # tilstand — hvad der er sket, og hvornår.
            afs = self.last_sender
            if afs is None:
                self._top_tekst.configure(text="👪  Fællestråd", fg=self._top)
                self._top_tegn.configure(text="")
            else:
                status, farve = self._samtalestatus(afs)
                tegn, tegnfarve = self._samtaletegn(afs)
                hvem = self.whitelist.get(afs, "").strip()
                indled = f"{hvem.upper()}   ·   " if hvem and hvem != "?" else ""
                self._top_tekst.configure(text=f"👪  {indled}{status}",
                                          fg=farve)
                self._top_tegn.configure(text=tegn, fg=tegnfarve)
            # Hjælpelinjen skal opdateres OGSÅ her. Før stod den her retur
            # øverst, og linjen blev derfor aldrig rørt i fællestråd — så
            # brugeren fik aldrig at vide, at Enter kvitterer. Fejlen kunne
            # ikke ses, fordi linjen slet ikke fandtes i knap-tilstand.
            self._opdater_hjaelpelinje(
                self.whitelist.get(afs, "") if afs is not None else None)
            return
        # Modtageren står nu FORREST og med ord ("Du skriver til: Mor").
        # Før var den eneste markering en lille ▶ inde i rækken af navne, og
        # den er let at overse — set i drift, hvor tre navne stod på skærmen,
        # og et tastetryk ikke lod til at gøre noget.
        valgt = self.selected or self.last_sender
        andre, navn = [], None
        for i, (cid, name) in enumerate(self.whitelist.items()):
            if i >= len(FKEYS):
                break
            if cid == valgt:
                navn = name
            else:
                andre.append(name)
        if navn is None and not andre:
            self._top_tekst.configure(text="Venter på familie…", fg=self._top)
            self._top_tegn.configure(text="")
        elif navn is None:
            self._top_tekst.configure(text="Vælg hvem du svarer", fg=self._top)
            self._top_tegn.configure(text="")
        else:
            # Navnet står med status og klokkeslæt i personens egen farve —
            # og samtalen er derfor fjernet fra listen i venstre side.
            # Intet skal stå to steder: listen er dem, der venter.
            status, _ = self._samtalestatus(valgt)
            tegn, tegnfarve = self._samtaletegn(valgt)
            self._top_tekst.configure(text=f"{navn.upper()}   ·   {status}",
                                      fg=self._personfarve(valgt))
            self._top_tegn.configure(text=tegn, fg=tegnfarve)
        self._tegn_sideliste()
        self._opdater_hjaelpelinje(navn)

    def _kvitter(self, chat_id: int | None, svarer: bool = False) -> None:
        """Fortæller afsenderen, at beskeden er set.

        Kvitteringen udløses af noget, brugeren GØR: vælger samtalen med en
        F-tast, ruller i den med piletasterne, eller svarer. Aldrig af, at
        skærmen tilfældigvis viste beskeden — så ville "set" betyde noget
        andet end det, familien tror, og det er værre end ingen kvittering.

        svarer=True: svaret er selv kvitteringen, så der sendes ikke en
        ekstra besked oveni."""
        # HVEM SKAL VIDE DET?
        #
        # I fællestråd ser alle alt — så hvis både datteren og svigersønnen
        # har skrevet, og hun trykker Enter, skal de BEGGE vide, at beskeden
        # er set. Før gik kvitteringen kun til den, der skrev sidst, og den
        # anden sad tilbage og ventede på et svar, der aldrig kom.
        #
        # I enkelte er én samtale én person, og så er det kun den ene.
        # DE VENTENDE ER FACIT — ikke whitelisten.
        #
        # Her stod før: tag whitelisten, og behold dem, der venter. Det lyder
        # ens, men det er det ikke. Bliver en person fjernet fra whitelisten,
        # MENS hendes besked stadig står ukvitteret, forsvandt hun ud af
        # listen — og så skete der INGENTING ved Enter. Ingen boble, intet
        # rødt mærke, der forsvandt. Brugeren trykker igen og igen, og
        # maskinen bliver ved med at sige, at der er noget nyt.
        #
        # En låst tilstand er det værste, denne maskine kan gøre: der er
        # ingen til at trykke sig ud af den.
        if self.config.mode == "faellestraad":
            modtagere = sorted(self._ukvitteret)
        else:
            modtagere = [chat_id] if chat_id in self._ukvitteret else []
        if not modtagere:
            return
        for c in modtagere:
            self._ukvitteret.discard(c)
        chat_id = modtagere[0]      # boblen hører til den viste samtale
        if svarer:
            # Svaret er selv kvitteringen. Der sendes ingen ekstra besked,
            # og der tegnes ingen ekstra boble — svarets egen boble står
            # der jo allerede.
            self._refresh_topbar()
            return

        # KVITTERINGEN SKAL KUNNE SES PÅ SKÆRMEN, ikke kun på telefonen.
        #
        # Før skete der to ting ved et tryk på Enter: familien fik 👁, og
        # hovedet ØVERST skiftede til "Læst 14.05". Men brugeren kigger på
        # tastaturet og på bunden af skærmen — ikke opad. For hende så det
        # ud, som om der ikke skete noget, og så trykker man igen.
        #
        # Samme lektie som skrivefeltet: svaret skal stå dér, hvor øjet er.
        #
        # Formen er en boble som alle andre. En linje, der forsvinder efter
        # et par sekunder, ville være ubrugelig for den, der kigger op ti
        # sekunder senere — og netop den slags kan en person med
        # hukommelsesbesvær ikke læne sig op ad.
        nu = datetime.now()
        try:
            gem_i_historik(self._history_path,
                           Incoming("Du", chat_id, "text",
                                    text=KVIT_TEKST, received=nu), egen=True)
        except Exception as e:
            log.warning("Kunne ikke gemme kvitteringen: %s", e)
        self._rows.append({"navn": "Du", "chat_id": chat_id, "type": "text",
                           "tekst": KVIT_TEKST, "fil": None,
                           "tid": nu.isoformat(), "egen": True})
        del self._rows[:-HISTORY_MAX]
        try:
            if (self.config.mode != "enkelte"
                    or str(self.selected) == str(chat_id)):
                tid = f"kl. {nu.strftime('%H.%M')} {self._day_label(nu).lower()}"
                if self.config.bubbles:
                    self._boble(KVIT_TEKST, tid, None, egen=True)
                else:
                    self._insert(f"{KVIT_TEKST} {tid}\n", tag="own")
                self._rul_til_bund()
        except tk.TclError:
            pass          # vinduet er lukket — kvitteringen sendes alligevel

        # Hovedet opdateres EFTER rækken er lagt ind, så statuslinjen kan
        # nå at læse den og skrive "Læst 14.05" i stedet for "Ny besked".
        self._refresh_topbar()
        # ÉN boble på skærmen, men besked til alle, der ventede. Hun har
        # jo læst det hele på én gang — det er én handling, ikke flere.
        #
        # HVEM FÅR BESKED — og med hvilke ord?
        #
        # I FÆLLESTRÅD: alle i tråden. Ikke kun dem, der lige har skrevet.
        #
        # Eksemplet, der afgjorde det: datteren skriver "vi henter dig kl.
        # 16". Det er ikke kun hende, der har brug for at vide, at han har
        # set det — svigersønnen, der skal køre, har brug for det samme.
        # Gik kvitteringen kun til den, der skrev, måtte han selv spørge
        # "har han nu set det?", og så er maskinen holdt op med at hjælpe.
        #
        # Derfor "jeres": det er gruppens samtale, der er læst.
        #
        # I ENKELTE: én samtale er én person, og så er det kun hende, det
        # angår. Der giver "din" mening, og "jeres" ville være forkert.
        #
        # Fjernet fra whitelisten = får ingenting. Skærmen er ryddet op
        # alligevel (se ovenfor) — det er to forskellige spørgsmål.
        if self.config.mode == "faellestraad":
            paa_listen = list(self.whitelist.ids())
            kvit_besked = f"👁  Jeres besked er læst kl. {nu.strftime('%H.%M')}"
        else:
            paa_listen = [c for c in modtagere if c in self.whitelist.ids()]
            kvit_besked = f"👁  Din besked er læst kl. {nu.strftime('%H.%M')}"
        if not paa_listen:
            return
        try:
            self.bot.send_text(paa_listen, kvit_besked)
        except Exception as e:
            log.warning("Kunne ikke sende kvittering til %s: %s", paa_listen, e)

    def _personfarve(self, chat_id: int | None) -> str:
        """Personens faste farve. Bestemmes af pladsen på whitelisten, så den
        er den samme, hver gang maskinen starter."""
        ids = self.whitelist.ids()
        if chat_id in ids:
            return PERSONFARVER[ids.index(chat_id) % len(PERSONFARVER)]
        return self._accent

    def _tegn_sideliste(self) -> None:
        """Tegner samtalelisten — men kun når den har ændret sig.

        Kaldes fra _refresh_topbar, som kører hvert 300. millisekund. Uden
        signaturtjekket ville hele listen blive bygget om tre gange i
        sekundet, dagen lang."""
        if self.sidebar is None:
            return
        sig = (tuple(self.whitelist.items()),
               self.selected or self.last_sender,
               tuple(sorted(self._venter)),
               tuple(sorted(self._ukvitteret)),
               # sidste besked pr. samtale — så statuslinjen følger med,
               # når der kommer svar eller nye beskeder
               tuple((str(r.get("chat_id")), r.get("tid"), r.get("egen"))
                     for r in self._rows[-1:]))
        if sig == self._side_sig:
            return
        self._side_sig = sig
        for w in self.sidebar.winfo_children():
            try:
                w.destroy()
            except tk.TclError:
                pass
        valgt = self.selected or self.last_sender
        vist = 0
        for i, (cid, navn) in enumerate(self.whitelist.items()):
            if i >= len(FKEYS):
                break
            if cid == valgt:
                continue          # står allerede i hovedet over beskederne
            farve = self._personfarve(cid)
            vist += 1
            # Listen indeholder KUN samtaler, der ikke er fremme (v4.29), så
            # ingen af dem kan være den valgte. Fremhævningen af den valgte
            # blev derfor fjernet — den var død kode, der lod, som om listen
            # kunne vise noget, den ikke kan.
            bg = self._btn
            ramme = tk.Frame(self.sidebar, bg=bg)
            ramme.pack(fill="x", pady=(0, 8))
            # Farvet stolpe i venstre kant — samme farve som personens bobler
            tk.Frame(ramme, bg=farve, width=6).pack(side="left", fill="y")
            tegn, tegnfarve = self._samtaletegn(cid)
            tk.Label(ramme, text=tegn, bg=bg, fg=tegnfarve,
                     font=self._font_name, padx=10).pack(side="right")
            tk.Label(ramme, text=FKEYS[i], bg=bg, fg=self._day,
                     font=self._font_tid, padx=8).pack(side="right")
            # Navn og status i to linjer. Ordene er valgt med omhu:
            # "Ny besked" fortæller, hvad der ER sket, og kan handles på.
            # "Ikke læst" fortæller, hvad der IKKE er sket — det er en
            # bebrejdelse, ikke en oplysning.
            status, statusfarve = self._samtalestatus(cid)
            spalte = tk.Frame(ramme, bg=bg)
            spalte.pack(side="left", fill="x", expand=True, padx=12, pady=12)
            tk.Label(spalte, text=navn, bg=bg, fg=self._fg,
                     font=self._font_name, anchor="w").pack(fill="x")
            tk.Label(spalte, text=status, bg=bg, fg=statusfarve,
                     font=self._font_tid, anchor="w").pack(fill="x")
        # Er der kun én person, er listen tom — så skal den heller ikke
        # optage bredde. Skærmen skal ikke bære et tomt felt hele dagen.
        if vist:
            if not self.sidebar.winfo_ismapped():
                self.sidebar.pack(side="left", fill="y", before=self.topbar)
        else:
            self.sidebar.pack_forget()

    def _samtalestatus(self, chat_id: int) -> tuple[str, str]:
        """Linjen under navnet i samtalelisten: hvad er der sket her?

        Kun ét af de tre svar kræver handling, og netop det står i personens
        egen farve. Resten er dæmpet, så øjet trækkes hen til det, der betyder
        noget."""
        # (tegn, farve) hentes af den, der viser status — se _samtaletegn
        if chat_id in self._venter or chat_id in self._ukvitteret:
            for r in reversed(self._rows):
                if str(r.get("chat_id")) == str(chat_id) and not r.get("egen"):
                    try:
                        naar = datetime.fromisoformat(r["tid"])
                        return (f"Ny besked {naar.strftime('%H.%M')}",
                                self._personfarve(chat_id))
                    except (KeyError, ValueError):
                        break
            return "Ny besked", self._personfarve(chat_id)
        # Den valgte samtale får IKKE "Vises nu". Den er allerede fremhævet
        # med farve, bredere stolpe og lysere bund — ordene bruges bedre på
        # at fortælle, hvad der skete sidst.
        for r in reversed(self._rows):
            if str(r.get("chat_id")) == str(chat_id):
                try:
                    naar = datetime.fromisoformat(r["tid"])
                except (KeyError, ValueError):
                    break
                if r.get("egen"):
                    # En kvittering er ikke et svar. Mærket i teksten er det,
                    # der skiller dem ad — også efter en genstart, hvor
                    # historikken kun har teksten at gå efter.
                    if str(r.get("tekst", "")).startswith(KVIT_MAERKE):
                        return f"Læst {naar.strftime('%H.%M')}", self._day
                    return f"Du svarede {naar.strftime('%H.%M')}", self._day
                return f"Læst {naar.strftime('%H.%M')}", self._day
        return "Ingen beskeder endnu", self._day

    def _samtaletegn(self, chat_id: int) -> tuple[str, str]:
        """Firkanten ved siden af navnet: fyldt+rød = ny, flueben+grøn = læst.

        Formen bærer betydningen lige så meget som farven, så den også virker
        for den, der ikke kan skelne rød og grøn."""
        if chat_id in self._venter or chat_id in self._ukvitteret:
            return "■", FARVE_NY
        return "✓", FARVE_LAEST

    def _opdater_hjaelpelinje(self, navn: str | None) -> None:
        """Skriver modtageren ind i linjen UNDER skrivefeltet.

        Grunden: mens man skriver, kigger man ned i feltet — men oplysningen
        om, hvem beskeden går til, stod øverst på skærmen. Svaret på "hvem
        skriver jeg til?" skal stå dér, hvor øjet er."""
        etiket = getattr(self, "_hjaelp", None)
        if etiket is None:
            return
        # Linjen skal sige, hvad Enter gør LIGE NU — ikke alt, hvad maskinen
        # kan. Den lange forklaring om autosend blev fjernet: den stod der
        # hele dagen og blev derfor ikke læst, når den betød noget.
        venter = (self.selected or self.last_sender) in self._ukvitteret
        # HVEM får det at vide? I fællestråd er svaret "gruppen", uanset hvem
        # der skrev sidst — brugeren svarer jo dem alle sammen. I enkelte er
        # det den ene, samtalen handler om. Ordet skal passe med det, der
        # faktisk sker, ellers lover linjen noget forkert.
        if self.config.mode == "faellestraad":
            hvem = "gruppen"
        elif navn and navn != "?":
            hvem = navn
        else:
            hvem = None

        if self.entry is None:
            # Knap-tilstand: Enter sender ikke, den kvitterer. Er der ikke
            # noget ukvitteret, tier linjen — en vejledning, der står hele
            # dagen, bliver ikke læst den dag, den betyder noget.
            if venter and hvem:
                tekst = f"Tryk ⏎ Enter — så ved {hvem}, at du har set beskeden"
            elif venter:
                tekst = "Tryk ⏎ Enter — så ved de, at du har set beskeden"
            else:
                tekst = ""
        elif venter and hvem:
            # Begge veje nævnes, fordi begge står åbne lige nu: skriv noget,
            # eller kvittér. Det er ikke to funktioner at lære — det er den
            # samme tast, der gør det, der giver mening.
            tekst = (f"Skriv en besked, eller tryk ⏎ Enter — "
                     f"så ved {hvem}, at du har set beskeden")
        elif venter:
            tekst = ("Skriv en besked, eller tryk ⏎ Enter — "
                     "så ved de, at du har set beskeden")
        elif hvem and self.config.mode != "faellestraad":
            tekst = f"Skriver til {hvem} — tryk ⏎ Enter"
        else:
            tekst = "Skriv her og tryk ⏎ Enter"
        try:
            etiket.configure(text=tekst)
        except tk.TclError:
            pass

    # -- indgående ------------------------------------------------------------

    def _poll_inbox(self) -> None:
        """DENNE LØKKE MÅ ALDRIG KUNNE DØ.

        Den er maskinens hørelse: uden den kommer ingen besked nogensinde
        på skærmen igen. Og den dør tavst — vinduet står, tasterne virker,
        rulningen virker. Processen lever, så genstartsvagten opdager
        ingenting. Maskinen er døv, og den ser rask ud.

        Sådan kunne det ske: en halvt skrevet eller defekt billedfil fik
        Pillow til at kaste en fejl. Fejlen røg ud af hele funktionen —
        FØR linjen, der bestiller næste gennemløb. Løkken stoppede for
        altid efter én ødelagt fil.

        To værn nu: hver besked har sin egen fejlgrænse, så én defekt
        besked ikke tager resten med sig — og næste gennemløb bestilles i
        en finally, så det sker, uanset hvad der går galt."""
        try:
            while True:
                try:
                    m = self.inbox.get_nowait()
                except queue.Empty:
                    break
                try:
                    self._modtag_til_skaerm(m)
                except Exception as e:
                    # Beskeden er allerede gemt i historikken af _modtag.
                    # Her er det VISNINGEN, der fejlede — så den skal
                    # nævnes på skærmen, ikke forsvinde.
                    log.warning("Kunne ikke vise besked fra %s: %s",
                                getattr(m, "sender_name", "?"), e)
                    navn = getattr(m, "sender_name", "familien")
                    try:
                        self._append_system(
                            f"⚠️ En besked fra {navn} kunne ikke vises")
                    except Exception:
                        pass
                    # LINJEN PÅ SKÆRMEN ER IKKE NOK.
                    #
                    # Den, der sidder foran skærmen, kan ikke gøre noget
                    # ved en besked, der ikke kunne tegnes — og i
                    # "enkelte"-tilstand bliver linjen tilmed visket ud,
                    # næste gang samtalen tegnes om. Den, der KAN gøre
                    # noget, er administrator, og han sidder et andet sted.
                    #
                    # Kun ÉN melding pr. opstart: er et bibliotek gået i
                    # stykker, fejler hver eneste besked, og tredive
                    # ens beskeder hjælper ingen.
                    if not self._visfejl_meldt:
                        self._visfejl_meldt = True
                        try:
                            self.bot.send_admin(
                                f"⚠️ {self.config.machine_name} kunne ikke "
                                f"VISE en besked fra {navn} på skærmen.\n"
                                f"Grund: {e}\n\n"
                                f"Beskeden er gemt i historikken, og "
                                f"maskinen kører videre — men den stod "
                                f"aldrig på skærmen, og han har ikke set "
                                f"den. Kig i loggen: journalctl -t livline\n\n"
                                f"Meldes kun én gang pr. opstart.")
                        except Exception as e2:
                            log.warning("Kunne ikke melde visningsfejl "
                                        "til admin: %s", e2)
            # Resultatet af egne afsendelser kommer fra en anden tråd og
            # behandles HER, hvor vi er i hovedtråden og må røre Tkinter.
            try:
                while True:
                    boble, ok = self._svarkoe.get_nowait()
                    self._tegn_sendefejl(boble, ok)
            except queue.Empty:
                pass
            self._refresh_topbar()  # whitelist kan ændres af /tilfoej undervejs
            self._vis_netstatus()
        except Exception as e:
            log.warning("Fejl i beskedløkken: %s", e)
        finally:
            # UANSET HVAD. Uden denne finally er maskinen døv for altid.
            try:
                self.root.after(300, self._poll_inbox)
            except tk.TclError:
                pass        # vinduet er lukket — så skal den heller ikke køre

    def _vis_netstatus(self) -> None:
        """Sætter netlinjen på skærmen, når Telegram ikke har kunnet nås.

        Pakkes kun om, når tilstanden SKIFTER. Et pack/pack_forget i hver
        runde ville få hele skærmen til at hoppe fire gange i sekundet."""
        try:
            nede = self.bot.net_nede_sek() > NET_STILLE_SEK
        except Exception:
            return              # botten er ikke klar endnu — ikke en fejl
        if nede == self._net_vist:
            return
        self._net_vist = nede
        if nede:
            # Lige under hovedet, før alt andet i den øvrige stak.
            self._netlinje.pack(after=self.topbar, fill="x")
            log.warning("Netlinjen er sat på skærmen — ingen kontakt i %d sek",
                        int(self.bot.net_nede_sek()))
        else:
            self._netlinje.pack_forget()
            log.info("Netlinjen er væk igen — forbindelsen er tilbage")

    def _modtag_til_skaerm(self, m: Incoming) -> None:
        """Én indgående besked: gem den i samtalen, og vis den — men KUN
        hvis den hører til den samtale, brugeren selv har valgt.

        Reglen er: skærmen skifter aldrig samtale af sig selv (v4.28).
        Kommer der besked fra en anden, giver maskinen lyd, blinker og
        markerer samtalen i listen — og bliver stående, hvor brugeren
        satte den. Et skift, hun ikke har bedt om, kan tage en besked væk,
        før den er læst.

        Eneste undtagelse: den allerførste besked på en frisk maskine, hvor
        ingen samtale er valgt endnu. Der er intet at miste, og uden den
        ville beskeden aldrig blive vist."""
        self._rows.append({"navn": m.sender_name, "chat_id": m.chat_id,
                           "type": m.kind, "tekst": m.text,
                           "fil": str(m.file_path) if m.file_path else None,
                           "tid": m.received.isoformat(), "egen": False})
        del self._rows[:-HISTORY_MAX]
        self._ukvitteret.add(m.chat_id)

        # Er der slet ikke valgt en samtale endnu (frisk maskine, tom skærm),
        # åbnes afsenderens. Det er det ENESTE nødvendige skift: der er intet
        # at miste, og uden det ville den allerførste besked aldrig blive vist.
        if self.config.mode == "enkelte" and self.selected is None:
            self.selected = m.chat_id
            self._tegn_samtale()

        if self.config.mode != "enkelte" or m.chat_id == self.selected:
            self._show(m)
            # HOVEDET SKAL OPDATERES HER — ikke som en bivirkning.
            #
            # Det gjorde det før kun gennem _flash(), som til sidst sætter
            # farverne rigtigt igen og dermed kom til at tegne hovedet. Det
            # virkede, så længe blinket var slået til. Sattes "blink": false,
            # stod der stadig "👪 Fællestråd" med en ulæst besked på skærmen,
            # det røde ■ kom aldrig, og hjælpelinjen fortalte aldrig, at
            # Enter kvitterer.
            #
            # At det virkede, var altså et held: en oplysning, brugeren skal
            # kunne stole på, hang på en animation. Kaldet står her nu —
            # EFTER _show, som sætter last_sender.
            self._refresh_topbar()
            return

        # To grunde til IKKE at springe:
        #   1. brugeren er midt i en sætning — den må ikke forsvinde
        #   2. den besked, der står nu, har ikke fået sin ro-tid endnu
        # I begge tilfælde venter samtalen som "●" i listen, og intet går
        # tabt: markeringen bliver stående, til brugeren selv går derhen.
        # SKÆRMEN SKIFTER ALDRIG SAMTALE AF SIG SELV.
        #
        # Beskeden giver lyd, blinker i topbaren og står som "Ny besked 14.03"
        # i listen — men skærmen bliver, hvor brugeren satte den. Et skift,
        # hun ikke selv har bedt om, kan tage en besked væk, før den er læst,
        # og gør maskinen uforudsigelig. Hun henter den nye samtale med
        # F-tasten, når hun er klar.
        self._venter.add(m.chat_id)
        self._refresh_topbar()
        self._flash()

    def _tegn_samtale(self) -> None:
        """Rydder skærmen og tegner den valgte samtale forfra.

        Prisen for at kunne skifte samtale er, at alt skal tegnes igen —
        derfor holdes historikken i hukommelsen. Med 100 beskeder tager det
        under et sekund, og det sker kun, når brugeren selv skifter."""
        # Boblerne er selvstændige widgets inde i tekstfeltet. Slettes teksten
        # uden at destruere dem, bliver de hængende usynligt — ved hvert skift
        # af samtale ville der samle sig flere og flere.
        for w in self.text.winfo_children():
            try:
                w.destroy()
            except tk.TclError:
                pass
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._img_refs.clear()
        self._nyeste = None
        self._tom_linje = False
        for r in self._rows:
            if (self.config.mode == "enkelte"
                    and str(r.get("chat_id")) != str(self.selected)):
                continue
            self._tegn_raekke(r)
        if self.text.index("end-1c") == "1.0":
            self._insert("Ingen beskeder i denne samtale endnu\n", tag="tom")
            self._tom_linje = True
        self._rul_til_bund()
        self._refresh_topbar()

    def _tegn_raekke(self, r: dict) -> None:
        """Tegner én gemt række — bruges både ved opstart og ved skift."""
        try:
            tid = datetime.fromisoformat(r["tid"])
            naar = f"kl. {tid.strftime('%H.%M')} {self._day_label(tid).lower()}"
            if r.get("egen"):
                self._boble(r.get("tekst", ""), naar, None, egen=True)
                return
            self._show(Incoming(
                sender_name=r["navn"], chat_id=int(r["chat_id"]),
                kind=r["type"], text=r.get("tekst", ""),
                file_path=Path(r["fil"]) if r.get("fil") else None,
                received=tid), replay=True)
        except Exception as e:
            log.warning("Sprang beskadiget historik-post over: %s", e)

    def _day_label(self, when: datetime) -> str:
        """'I dag' / 'I går' / 'mandag 27. juli' — hjælper brugeren med at
        se, hvornår beskeden kom, uden at skulle regne på datoer."""
        today = datetime.now().date()
        d = when.date()
        if d == today:
            return "I dag"
        if (today - d).days == 1:
            return "I går"
        uger = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag",
                "lørdag", "søndag"]
        mdr = ["januar", "februar", "marts", "april", "maj", "juni", "juli",
               "august", "september", "oktober", "november", "december"]
        return f"{uger[d.weekday()]} {d.day}. {mdr[d.month - 1]}"

    def _ryd_tom_linje(self) -> None:
        """Fjerner "Venter på beskeder…" ved den første rigtige besked."""
        if getattr(self, "_tom_linje", False):
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.configure(state="disabled")
            self._tom_linje = False

    def _show(self, m: Incoming, replay: bool = False) -> None:
        """replay=True: beskeden genvises fra historikken ved opstart —
        ingen lyd, intet blink, og medier afspilles ikke af sig selv."""
        self._ryd_tom_linje()
        self.last_sender = m.chat_id
        stamp = m.received.strftime("%H.%M")
        dag = self._day_label(m.received).lower()
        tid = f"kl. {stamp} {dag}"

        if self.config.bubbles and m.kind == "text":
            self._boble(m.text, tid, m.sender_name,
                        farve=(self._personfarve(m.chat_id)
                               if self.config.mode == "enkelte" else None))
            self._rul_til_bund()
            if not replay:
                self._flash()
            return

        # Uden bobler (eller ved medier): afsenderlinje + indhold
        self._insert(f"{m.sender_name}  ·  {tid}\n", tag="name")

        if m.kind == "text":
            self._insert(m.text + "\n")
        elif m.kind == "photo":
            if m.file_path and m.file_path.exists():
                self._insert_photo(m.file_path)
            else:
                self._insert("(billede)\n")
            if m.text:
                self._insert(m.text + "\n")
        elif m.kind == "voice":
            # "voice" og "video" står stadig i historikken fra ældre
            # versioner. Ingen af delene afspilles længere — linjen bliver
            # stående, så en gammel samtale ikke får huller i sig.
            self._insert("🎙  Talebesked — kan desværre ikke vises her\n")

        self._rul_til_bund()
        if replay:
            return
        # HER LÅ ET BIP. Det er slået fra sammen med talebeskederne.
        #
        # Maskinen bippede døgnet rundt — også kl. 2, når barnebarnet
        # skrev. Skærmen er sort om natten, men lyden var det ikke.
        # Og der er ingen at skrue ned for den: han har otte taster.
        #
        # MASKINEN LAVER ALDRIG LYD. At der er en ny besked, siges med
        # det røde ■ i hovedet og et kort blink i kanten — begge dele
        # synlige på afstand, ingen af dem i stand til at vække nogen.
        self._flash()      # visuelt signal: kanten blinker kort

    def _flash(self, times: int = 4) -> None:
        """Dæmpet puls i topbaren ved ny besked — synligt på afstand, men
        uden at hele skærmen skifter farve (det virkede uroligt)."""
        if not self.config.blink:
            return
        # Pulsen skal ramme både rammen og de to etiketter — ellers blinker
        # kun baggrunden omkring teksten, og det ser ud som en fejl.
        def maal(bg):
            for w in (self.topbar, self._top_midte,
                      self._top_tekst, self._top_tegn):
                w.configure(bg=bg)
        if times <= 0:
            maal(self._bg)
            self._refresh_topbar()      # farverne sættes rigtigt igen
            return
        maal(self._accent if times % 2 == 0 else self._bg)
        self.root.after(320, lambda: self._flash(times - 1))

    def _boble(self, tekst: str, tid: str, afsender: str | None,
               egen: bool = False, farve: str | None = None):
        """Tegner én besked som en boble med kant. Modtagne bobler står til
        venstre med afsenderens navn øverst; egne svar står til højre."""
        # Den forrige "nyeste" boble sættes tilbage til normal kant
        if getattr(self, "_nyeste", None) is not None:
            try:
                self._nyeste.configure(highlightthickness=2,
                                       highlightbackground=self._nyeste_kant)
            except tk.TclError:
                pass

        # farve = personens egen farve (enkelte-tilstand). Uden den ser alle
        # afsendere ens ud, og så er farven i listen kun pynt.
        kant = self._kant_ud if egen else (farve or self._kant_ind)
        fyld = self._boble_ud if egen else (
            _bland(self._bg, farve, 0.18) if farve else self._boble_ind)
        ramme = tk.Frame(self.text, bg=fyld,
                         highlightthickness=4,          # nyeste besked
                         highlightbackground=self._accent,
                         padx=18, pady=12)
        self._nyeste, self._nyeste_kant = ramme, kant
        # Overskrift: "Mette sendte" / "Du sendte" — retningen står altså
        # også med ord, ikke kun med placering og farve
        overskrift = "Du sendte" if egen else (
            f"{afsender} sendte" if afsender else None)
        if overskrift:
            tk.Label(ramme, text=overskrift, font=self._font_name,
                     bg=ramme["bg"],
                     fg=self._kant_ud if egen else (farve or self._accent),
                     anchor="e" if egen else "w").pack(fill="x")
        tk.Label(ramme, text=tekst, font=self._font_body, bg=ramme["bg"],
                 fg=self._fg, justify="left", anchor="w",
                 # Samme ombrydningsbredde som SKRIVEFELTET. Før stod der
                 # 0,92 af spalten — 8 % smallere — og en sætning, der lige
                 # passede i feltet, tabte derfor et par bogstaver ned på
                 # næste linje, så snart den blev til en boble. Boblens egen
                 # luft (padx 18) og kant (4) trækkes fra, så boblens YDRE
                 # bredde bliver spalten, præcis som feltets.
                 wraplength=max(120, self._spalte()[1] - 2 * 18 - 2 * 4)
                 ).pack(fill="x")
        tk.Label(ramme, text=tid, font=self._font_tid, bg=ramme["bg"],
                 fg=self._day, anchor="e").pack(fill="x")

        self.text.configure(state="normal")
        start = self.text.index("end-1c")
        self.text.window_create("end", window=ramme, pady=10)
        self.text.insert("end", "\n")
        self.text.tag_add("hoejre" if egen else "venstre", start, "end-1c")
        self.text.configure(state="disabled")
        self._img_refs.append(ramme)      # hold rammen i live
        return ramme

    def _insert(self, s: str, tag: str | None = None) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", s, tag or "std")   # "std" styrer justeringen
        self.text.configure(state="disabled")

    def _billed_maks(self) -> tuple[int, int]:
        """Hvor stort et billede må vises. Bredden følger beskedspalten,
        præcis som boblerne og skrivefeltet — ikke skærmen."""
        return (max(400, self._spalte()[1]),
                int(self.root.winfo_screenheight() * 0.85))

    def _insert_photo(self, path: Path) -> None:
        img = Image.open(path)
        # Liggende billeder må fylde mere af skærmhøjden end stående.
        # Grunden er geometrisk: et 4:3-foto på en 16:9-skærm rammer
        # højdegrænsen, længe før det når kanterne i bredden — mens et
        # stående foto fylder højden af sig selv.
        bredde, hoejde = self._billed_maks()
        if img.width > img.height:
            # Liggende: lad bredden bestemme, så billedet fylder skærmen.
            # Det bliver højere end skærmen, og brugeren ruller lidt —
            # bedre end et lille billede midt i en tom flade.
            hoejde = int(self.root.winfo_screenheight() * 1.6)
        img.thumbnail((bredde, hoejde))
        photo = ImageTk.PhotoImage(img)
        self._img_refs.append(photo)
        self.text.configure(state="normal")
        start = self.text.index("end-1c")
        self.text.image_create("end", image=photo, padx=10, pady=10)
        self.text.insert("end", "\n")
        # "billede"-mærket centrerer uden indrykning, så billedet må fylde
        # hele bredden, selv om teksten er begrænset (2.15)
        self.text.tag_add("billede", start, "end-1c")
        self.text.configure(state="disabled")

    def _append_system(self, s: str) -> None:
        self._insert(s + "\n", tag="name")
        self._rul_til_bund()

    # -- udgående: faste svar ---------------------------------------------------

    def _kladde(self) -> str:
        """Det, der står i skrivefeltet lige nu."""
        if self.entry is None:
            return ""
        return self.entry.get("1.0", "end").strip()

    def _ryd_kladde(self) -> str:
        """Tømmer skrivefeltet og sætter det tilbage til FELT_MIN linjer."""
        if self.entry is not None:
            self.entry.delete("1.0", "end")
            self.entry.configure(height=FELT_MIN)
        return "break"

    def _kladde_aendret(self, _event=None) -> None:
        """Kaldes ved hvert tastetryk. Selve målingen udskydes til Tk har
        ombrudt teksten færdigt — ellers måles på gårsdagens linjer."""
        if self.entry is not None:
            self.root.after_idle(self._juster_hoejde)

    def _spalte(self) -> tuple[int, int]:
        """Beskedspalten: (indrykning i tekstfeltet, spaltens bredde).

        ÉN REGEL FOR HELE SKÆRMEN. Før blev boblernes bredde regnet ud af
        SKÆRMEN, mens den spalte, de skulle stå i, blev regnet ud af
        tekstfeltet — som er smallere, fordi samtalelisten tager af
        venstresiden. Resultatet: en egen besked er højrestillet, blev
        bredere end sin spalte og løb ud over VENSTRE kant med halve
        bogstaver. Præcis samme fejl som skrivefeltet havde, bare et
        andet sted.

        Der måles på tekstfeltet, ikke på skærmen, og der måles EFTER
        opsætningen — samtalelisten skifter bredde, når navne kommer og
        går."""
        b = self.text.winfo_width()
        if b <= 1:                       # endnu ikke tegnet
            b = self.root.winfo_screenwidth()
        brugbar = max(200, b - 2 * self.config.margin)
        bredde = max(200, int(brugbar * self.config.text_width))
        ind = max(0, (brugbar - bredde) // 2)
        return ind, bredde

    def _juster_bredder(self) -> None:
        """Retter beskedspalten til efter den plads, tekstfeltet faktisk
        har fået — og lægger derefter skrivefeltet i samme spalte."""
        try:
            ind, _ = self._spalte()
            for mærke in ("std", "name", "own", "venstre", "hoejre"):
                self.text.tag_configure(mærke, lmargin1=ind, lmargin2=ind,
                                        rmargin=ind)
        except tk.TclError:
            return
        self._juster_knapper()
        self._juster_feltbredde()

    def _juster_knapper(self) -> None:
        """Holder svarknapperne inden for skærmen.

        Set i drift med fem svar på en 1366 px skærm: knapperne lå på én
        række uden at bryde teksten, så rækken blev bredere end skærmen og
        de yderste svar var skåret af. Fjerde gang samme rod — noget, der
        skal fylde noget, regnede sin egen bredde ud i stedet for at
        spørge.

        Hver knap får den plads, den faktisk har fået, minus sin egen luft.
        Er der fem svar, brydes teksten i stedet for at skubbe."""
        if not getattr(self, "_knapper", None):
            return
        try:
            b = self.root.winfo_width()
            if b <= 1:
                b = self.root.winfo_screenwidth()
            # padx=12 i hver side pr. knap, plus rammens egen sidemargen
            pr_knap = (b - 2 * self.config.margin) // len(self._knapper)
            wrap = max(80, pr_knap - 2 * 12 - 24)
            for knap in self._knapper:
                knap.configure(wraplength=wrap)
        except tk.TclError:
            return

    def _juster_feltbredde(self) -> None:
        """Lægger skrivefeltet i samme spalte som beskedboblerne.

        Set i drift: feltet begyndte 217 px længere til venstre end nogen
        boble, fordi det blev centreret i HELE vinduet, mens beskederne
        centreres inde i tekstfeltet — som starter til højre for
        samtalelisten. To regler for det samme sted.

        Der måles på det, der står på skærmen, og ikke på tal gættet ved
        opbygningen: samtalelisten skifter bredde, når navne kommer og går.

        Fremgangsmåden: sæt margenen til nul, mål hvor meget plads rammen
        får, og regn derefter den margen ud, der lægger feltet præcis i
        beskedernes spalte. Uden nulstillingen ville man måle sin egen
        forrige margen med."""
        if self.entry is None:
            return
        try:
            self._felt_wrap.pack_configure(padx=0)
            self.root.update_idletasks()
            plads_v = self._felt_wrap.winfo_rootx()
            plads_b = self._felt_wrap.winfo_width()
            tekst_v = self.text.winfo_rootx()
            tekst_b = self.text.winfo_width()
            if plads_b <= 1 or tekst_b <= 1:
                self.root.after(200, self._juster_feltbredde)
                return
            # Beskedernes venstre kant: tekstfeltets margen plus den
            # indrykning, "tekstbredde" giver.
            ind, bredde = self._spalte()
            venstre = tekst_v + self.config.margin + ind
            luft_v = max(0, venstre - plads_v)
            luft_h = max(0, (plads_v + plads_b) - (venstre + bredde))
            self._felt_wrap.pack_configure(padx=(luft_v, luft_h))
        except tk.TclError:
            pass

    def _juster_hoejde(self) -> None:
        """Lader feltet vokse med teksten — højst seks linjer, så beskederne
        på skærmen ikke bliver klemt sammen.

        NB: der skal tælles OMBRUDTE linjer ("displaylines"), ikke linjeskift.
        Enter sender jo beskeden, så brugeren indsætter aldrig et linjeskift —
        og et felt, der talte dem, voksede derfor aldrig (fejl i 4.9)."""
        if self.entry is None:
            return
        try:
            c = self.entry.count("1.0", "end-1c", "displaylines")
            # Tk returnerer antallet af linjeskift i visningen: 0 for én
            # linje, og None hvis feltet er tomt. Derfor +1.
            antal = (c[0] if isinstance(c, (tuple, list)) else c) or 0
            ny = max(FELT_MIN, min(FELT_MAX, antal + 1))
            if ny != int(self.entry.cget("height")):
                self.entry.configure(height=ny)
        except (tk.TclError, ValueError, TypeError):
            pass          # målingen må aldrig kunne vælte appen

    def _autosend_check(self) -> None:
        """Sender af sig selv, hvis der står tekst i feltet, og brugeren ikke
        har rørt tastaturet et stykke tid.

        Grunden: den fejl, brugeren IKKE kan opdage, er den farlige. Glemmer
        hun at trykke Enter, tror hun, familien har fået beskeden — og teksten
        forsvinder ved den daglige nedlukning kl. 22. Hellere en besked, der
        er sendt lidt tidligt, end en besked, der aldrig kom af sted.
        Slås fra med "autosend": 0 i config."""
        try:
            if (self.config.autosend > 0 and self._kladde()
                    and time.monotonic() - self._last_key >= self.config.autosend):
                log.info("Sender kladde automatisk efter %d sek. uden tastetryk",
                         self.config.autosend)
                self._send_typed(auto=True)
        except Exception:                       # må aldrig stoppe løkken
            log.exception("Fejl i autosend")
        self.root.after(3_000, self._autosend_check)

    def _send_typed(self, auto: bool = False) -> None:
        """Sender det, brugeren selv har skrevet.

        auto=True: afsendelsen kom fra autosend (5 minutter uden tastetryk).
        Så skiftes der IKKE samtale bagefter — brugeren er efter alt at dømme
        gået fra maskinen, og et skift, ingen ser, er værre end ingenting.
        Skiftet hører til det bevidste tryk på Enter."""
        txt = self._kladde()
        if not txt:
            # Tomt felt + Enter = "jeg har set det". Ét tastetryk betyder det
            # samme hele tiden: kvitter. Er der skrevet noget, sendes det —
            # er der ikke, kvitteres der bare. Brugeren skal ikke lære to ting.
            if not auto:
                self._kvitter(self.selected or self.last_sender)
            return
        self._ryd_kladde()
        self._send_reply(txt)

    def _send_reply(self, reply_text: str) -> None:
        # ÉN FINGER, ÉN BESKED.
        #
        # Set i drift: holdes en svartast nede, gentager tastaturet den
        # mange gange i sekundet, og familien får en byge af ens beskeder.
        # For dem ligner det panik. For hende skete der ingenting synligt
        # ud over, at boblerne blev ved med at komme.
        #
        # Kun det SAMME svar bremses, og kun i få sekunder. Et andet svar
        # går igennem med det samme — det er en ny beslutning, og den må
        # aldrig vente.
        nu_m = time.monotonic()
        # To værn, fordi ét ikke var nok.
        #
        # Det første fanger en tast, der holdes nede: samme svar igen
        # inden for få sekunder.
        #
        # Det andet kom til, fordi det første kunne omgås af en urolig
        # hånd: Q, X, Q, X skiftevis er aldrig "samme svar", så alt slap
        # igennem. Familien fik "Tak, Nej tak, Tak, Nej tak" i en lang
        # strøm — og for dem ligner det panik, ikke en skælvende finger.
        #
        # Ingen sender fire forskellige svar på ti sekunder med vilje.
        self._svar_tider = [t for t in self._svar_tider
                            if nu_m - t < SVAR_VINDUE_SEK]
        ens = (reply_text == self._sidste_svar_tekst
               and nu_m - self._sidste_svar < SVAR_PAUSE_SEK)
        for_mange = len(self._svar_tider) >= SVAR_MAKS_I_VINDUE
        if ens or for_mange:
            if not self._svar_spaerret:
                self._svar_spaerret = True
                log.info("Svar bremset (%s) — tast holdt nede eller urolig hånd?",
                         "gentaget" if ens else
                         f"{len(self._svar_tider)} svar på "
                         f"{SVAR_VINDUE_SEK:.0f} sek.")
            return
        self._svar_spaerret = False
        self._sidste_svar = nu_m
        self._sidste_svar_tekst = reply_text
        self._svar_tider.append(nu_m)

        self._ryd_tom_linje()
        rec = self._recipients()
        if not rec:
            self._append_system("Ingen at svare endnu — vent på en besked.")
            return
        # Er der ingen valgt samtale, sendes svaret til den, der skrev sidst
        # — og så SKAL den samtale også være den viste. Ellers gemmes svaret
        # under ét chat_id, mens skærmen filtrerer på et andet: boblen ses et
        # øjeblik og forsvinder ved næste gentegning.
        # (Mistænkt årsag til "den viser ikke altid, at jeg har sendt noget".)
        if self.config.mode == "enkelte" and self.selected != rec[0]:
            self.selected = rec[0]
        for cid in rec:
            self._kvitter(cid, svarer=True)
        nu = datetime.now()
        # Gem også egne svar, så samtalen er komplet efter en genstart
        gem_i_historik(self._history_path,
                       Incoming("Du", rec[0], "text", text=reply_text,
                                received=nu), egen=True)
        self._rows.append({"navn": "Du", "chat_id": rec[0], "type": "text",
                           "tekst": reply_text, "fil": None,
                           "tid": nu.isoformat(), "egen": True})
        del self._rows[:-HISTORY_MAX]
        # Statuslinjen i listen skal skifte til "Du svarede" med det samme.
        # Uden dette ventede den på næste gennemløb — op mod et tredjedels
        # sekund, hvor listen sagde noget, der ikke længere var sandt.
        self._refresh_topbar()
        tid = f"kl. {nu.strftime('%H.%M')} {self._day_label(nu).lower()}"
        if self.config.bubbles:
            boble = self._boble(reply_text, tid, None, egen=True)
        else:
            boble = None
            self._insert(f"Du svarede {self._recipient_label(rec)}: "
                         f"{reply_text}\n", tag="own")
        self._rul_til_bund()

        # Send, og vis resultatet — men gennem en KØ, ikke direkte.
        #
        # Svaret fra Telegram kommer i en timer-tråd. Tkinter må kun røres
        # fra hovedtråden; gør man det alligevel, er straffen ikke en pæn
        # fejlmeddelelse, men et sporadisk nedbrud eller en brugerflade,
        # der holder op med at tegne. Det er den værste slags fejl her:
        # den rammer sjældent, tilfældigt, og aldrig mens man kigger.
        # Derfor lægges resultatet i en kø, som _poll_inbox tømmer i
        # hovedtråden — samme vej som indgående beskeder allerede går.
        self.bot.send_text(rec, reply_text,
                           svar=lambda ok, b=boble: self._svarkoe.put((b, ok)))

    def _tegn_sendefejl(self, boble, ok: bool) -> None:
        """Markerer en boble, hvis beskeden ikke kunne sendes. Kaldes KUN
        fra hovedtråden, via køen i _poll_inbox."""
        if ok or boble is None:
            return
        try:
            boble.configure(highlightbackground=REC, highlightthickness=4)
            tk.Label(boble, text="⚠ Kunne ikke sendes — prøv igen",
                     font=self._font_tid, bg=boble["bg"], fg=REC,
                     anchor="e").pack(fill="x")
        except tk.TclError:
            pass

    def _recipient_label(self, rec: list[int]) -> str:
        if self.config.mode == "faellestraad":
            return "alle"
        return self.whitelist.get(rec[0]) if rec else "?"


def selvtest() -> int:
    """Bygger hele brugerfladen og lukker den igen. Bruges af /opdater til
    at afgøre, om en ny version overhovedet kan starte, FØR den installeres.
    Køres i et usynligt skærmmiljø: xvfb-run python3 livline_bot.py --selftest
    Bot-laget startes ikke — kun vinduet, som er der, fejlene sidder.

    BEGGE betjeningsformer bygges, uanset hvad maskinen selv bruger. En fejl
    i skrivefeltet ville ellers først vise sig på den første maskine, der
    havde det slået til — og der er sikkerhedsnettet ikke længere til stede."""
    grund = Config.load()
    for text_input in (False, True):
        c = replace(grund, text_input=text_input)
        ui = LivlineUI(c)
        ui._load_history()
        ui._show(Incoming("Prøve", 1, "text", text="Prøvebesked"), replay=True)
        if text_input:
            # Skriv i feltet og lad Enter-bindingen køre hele vejen igennem.
            # Uden godkendte modtagere sender _send_reply ikke noget — den
            # skriver "Ingen at svare endnu" — men koden er kørt.
            ui.entry.insert("1.0", "prøvetekst")
            ui._kladde_aendret()
            ui._send_typed()
            assert ui._kladde() == "", "skrivefeltet blev ikke tømt"
            ui._autosend_check()
        ui.root.after(300, ui.root.destroy)
        ui.root.mainloop()
    print("selvtest ok")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selvtest())
    LivlineUI(Config.load()).run()

#!/usr/bin/env bash
# Livline-PC installationsscript (Ubuntu 26.04 LTS)
INSTALL_VER="4.93"
# Brug:  sudo bash install.sh
# Forudsætning: livline_bot.py ligger i samme mappe.
#
# INSTALL_VER står i linje 3, så man kan se hvilket script man har uden at
# læse det. Scriptet og programmet skal følges ad: en gist, hvor kun den ene
# fil blev opdateret, er set flere gange, og fejlen viser sig først, når
# installationen mangler noget, den nye app regner med. Derfor afbryder
# scriptet, hvis de to numre ikke er ens.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Kør med sudo."; exit 1; fi
HERE="$(cd "$(dirname "$0")" && pwd)"

# ER DET OVERHOVEDET PROGRAMMET? Set i drift tre gange: den forkerte fil
# blev lagt i gisten (prøvefilen livline-test.py), og fejlen viste sig
# først, da maskinen ikke ville starte. Filen skal indeholde både
# versionsnummeret og brugerfladen for at være det rigtige program.
if [[ ! -f "$HERE/livline_bot.py" ]]; then
    echo "FEJL: livline_bot.py findes ikke i $HERE"; exit 1
fi
if ! grep -q '^VERSION = "' "$HERE/livline_bot.py" \
   || ! grep -q '^class LivlineUI' "$HERE/livline_bot.py"; then
    echo "FEJL: $HERE/livline_bot.py ligner ikke Livline-programmet."
    echo "      (mangler VERSION eller class LivlineUI — er det prøvefilen?)"
    exit 1
fi
APP_VER=$(grep -m1 '^VERSION = "' "$HERE/livline_bot.py" | cut -d'"' -f2)
DOC_VER=$(grep -m1 '^VERSION ' "$HERE/livline_bot.py" | awk '{print $2}')

# Filens eget hoved skal sige det samme som konstanten. Stod der før 4.35
# øverst i en fil, der kørte 4.51 — og hovedet er det, mennesker læser.
if [[ "$DOC_VER" != "$APP_VER" ]]; then
    echo "FEJL: livline_bot.py siger v$DOC_VER øverst, men VERSION = $APP_VER."
    echo "      Filen er redigeret halvt. Hent den frisk fra gisten."
    exit 1
fi
if [[ "$INSTALL_VER" != "$APP_VER" ]]; then
    echo "FEJL: install.sh er v$INSTALL_VER, men livline_bot.py er v$APP_VER."
    echo "      Kun den ene fil er opdateret i gisten. Hent begge igen."
    exit 1
fi

echo "== Livline-PC installation (app v$APP_VER · install.sh v$INSTALL_VER) =="
# -s: tokenen vises ikke på skærmen. Den er maskinens eneste hemmelighed,
# og en installation foregår ofte med nogen kigger med.
read -rsp "Bot-token (fra @BotFather): " TOKEN; echo
read -rp "Dit admin chat_id (din egen Telegram): " ADMIN_ID
[[ "$ADMIN_ID" =~ ^-?[0-9]+$ ]] || { echo "FEJL: chat_id skal være et tal."; exit 1; }
[[ "$TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] || {
    echo "FEJL: tokenen ser ikke rigtig ud (forventet form 123456789:AA…)."; exit 1; }
read -rp "Maskinnavn (fx 'Farmors Livline'): " MACHINE_NAME
read -rp "Tilstand [faellestraad/enkelte] (enter = faellestraad): " MODE
MODE=${MODE:-faellestraad}
[[ "$MODE" == "faellestraad" || "$MODE" == "enkelte" ]] || {
    echo "FEJL: tilstand skal være faellestraad eller enkelte."; exit 1; }
read -rp "Update-URL til /opdater (enter = slået fra): " UPDATE_URL
UPDATE_URL=${UPDATE_URL:-}

# SIGNERING SKAL VÆRE OBLIGATORISK, NÅR /opdater ER TÆNDT.
#
# Appen kontrollerer kun underskriften, hvis /etc/livline/opdater.pub
# findes — og installationen lagde den aldrig på. En ny maskine med en
# update-URL tog derfor imod hvad som helst fra den adresse og kørte det.
# Det er fail-OPEN, og det er den forkerte vej: en overtaget GitHub-konto
# eller en ændret adresse var nok til at få egen kode ind i en stue.
#
# Nu er det fail-CLOSED. Er der en update-URL, skal der være en nøgle,
# ellers slås /opdater fra. Syntakstjek og prøvekørsel viser, at kode KAN
# køre — de siger intet om, hvem der har sendt den.
#
# Nøglen skal komme et andet sted fra end koden. Ligger de begge i det
# samme repo, beskytter underskriften mod ingenting. Derfor en fil, du
# har med — typisk fra USB-nøglen, hvor sikkerhedskopien også ligger.
NOEGLEFIL=""
if [[ -n "$UPDATE_URL" ]]; then
    echo
    echo "/opdater kræver den OFFENTLIGE nøgle (opdater.pub), så maskinen kan"
    echo "kontrollere, at en ny version er underskrevet af dig. Den ligger"
    echo "typisk på din USB-nøgle. Uden den slås /opdater fra."
    read -rp "  Sti til opdater.pub (enter = slå /opdater fra): " NOEGLEFIL
    if [[ -z "$NOEGLEFIL" ]]; then
        echo "  /opdater SLÅS FRA — ingen nøgle angivet."
        echo "  Maskinen opdateres i stedet i hånden over Tailscale."
        UPDATE_URL=""
    elif [[ ! -f "$NOEGLEFIL" ]]; then
        echo "  FEJL: '$NOEGLEFIL' findes ikke. /opdater slås fra."
        UPDATE_URL=""; NOEGLEFIL=""
    elif ! openssl pkey -pubin -in "$NOEGLEFIL" -noout 2>/dev/null; then
        # En fil, der ikke ER en offentlig nøgle, ville give en maskine,
        # der afviser ALLE opdateringer — og fejlen ville først vise sig
        # den dag, du havde travlt med at rette noget.
        echo "  FEJL: '$NOEGLEFIL' er ikke en gyldig offentlig nøgle."
        echo "  (Kontrollér med: openssl pkey -pubin -in FIL -noout)"
        echo "  /opdater slås fra."
        UPDATE_URL=""; NOEGLEFIL=""
    else
        echo "  nøglen ser rigtig ud ✔"
    fi
fi

# NØDNETTET. Det net, maskinen kan finde, når familiens eget er væk, og du
# står i stuen med telefonen som hotspot. Uden det skal der kabel eller
# tastatur til — og tastaturet ligger under et stykke papir.
#
# Navn og kode står IKKE i scriptet, selv om det ville være nemmere. Filen
# her ligger i et offentligt repo: enhver kunne så lave et net med samme
# navn og kode i nærheden af maskinen, og maskinen ville koble sig på det
# af sig selv. Du taster dem i stedet — det er dit eget nødnet, og du
# kender det udenad.
#
# ENTER SPRINGER OVER. En maskine uden nødnet er bedre end en installation,
# der går i stå, fordi nogen ikke kunne huske koden.
echo
echo "Nødnet (valgfrit): det net, maskinen tager, når familiens er væk."
echo "Typisk din telefons hotspot. Tryk blot Enter for at springe over."
read -rp "  Navn på nødnettet (enter = intet): " NOEDNET
NOEDPSK=""
if [[ -n "$NOEDNET" ]]; then
    read -rsp "  Kode til \"$NOEDNET\" (mindst 8 tegn): " NOEDPSK; echo
    if [[ ${#NOEDPSK} -lt 8 ]]; then
        echo "  FEJL: koden skal være mindst 8 tegn. Nødnettet springes over."
        NOEDNET=""; NOEDPSK=""
    else
        # Tastes to gange. Koden kan ikke ses, mens den skrives, og en
        # tastefejl ville først vise sig den dag, maskinen skulle bruge
        # nettet — altså netop når intet andet virker.
        read -rsp "  Skriv den igen: " NOEDPSK2; echo
        if [[ "$NOEDPSK" != "$NOEDPSK2" ]]; then
            echo "  FEJL: de to koder er ikke ens. Nødnettet springes over."
            NOEDNET=""; NOEDPSK=""
        fi
        NOEDPSK2=""
    fi
fi
# Kiosk-bruger: SKAL være den bruger, den grafiske session logger ind som,
# ellers starter appen aldrig. Vi foreslår derfor den bruger, GDM allerede
# har autologin på (typisk den, du oprettede under Ubuntu-installationen),
# og ellers den eneste rigtige bruger på maskinen.
GDM_CONF=$(ls /etc/gdm*/custom.conf 2>/dev/null | head -1 || true)
SUGGESTED=""
[[ -n "$GDM_CONF" ]] && SUGGESTED=$(grep -oP '^AutomaticLogin=\K.*' "$GDM_CONF" 2>/dev/null || true)
[[ -z "$SUGGESTED" ]] && SUGGESTED=$(awk -F: '$3>=1000 && $3<65534 {print $1}' /etc/passwd | head -1)
SUGGESTED=${SUGGESTED:-livline}
read -rp "Kiosk-brugernavn (enter = $SUGGESTED): " KIOSK_USER
KIOSK_USER=${KIOSK_USER:-$SUGGESTED}
if ! id -u "$KIOSK_USER" &>/dev/null; then
    echo "ADVARSEL: brugeren '$KIOSK_USER' findes ikke og bliver oprettet."
    echo "Er det ikke den bruger, skærmen logger ind som, starter appen aldrig."
    read -rp "Fortsæt? [j/N]: " SVAR
    [[ "$SVAR" =~ ^[jJyY]$ ]] || { echo "Afbrudt."; exit 1; }
fi

echo "-- Installerer pakker..."
# Et spejl, der hikker, må ikke kunne stoppe en installation. Set i drift:
# dk.archive.ubuntu.com var midt i en synkronisering, apt-get update fejlede,
# og set -e afbrød hele scriptet — på en maskine, hvor hver eneste pakke i
# forvejen var installeret. Fejler det HER, går vi videre med de lister,
# maskinen allerede har; mangler der reelt en pakke, råber install nedenfor.
apt-get update -q || echo "   ADVARSEL: pakkelisterne kunne ikke hentes fuldt ud"
apt-get install -y -q python3 python3-pip python3-venv python3-tk python3-pil \
    python3-pil.imagetk \
    xvfb smartmontools fonts-noto-color-emoji cron openssl
#   INGEN AFSPILLER OG INGEN LYDPAKKER. mpv, ffmpeg og alsa-utils er væk.
#                     Livline er skærm og tastatur: video vises ikke,
#                     talebeskeder afspilles ikke, og maskinen bipper ikke.
#                     Lyd er telefonens arbejde — og i den aldersgruppe
#                     høres en besked bedre i et høreapparat end i en
#                     højttaler i en stue.
#   xvfb            → /opdater prøvekører en ny version, før den installeres
#   smartmontools   → diskens SMART-status med i heartbeat
#   noto-color-emoji→ giver emoji en chance for at vises (test på skærmen!)
#   cron            → uden den virker INGEN af de fire tidsstyrede opgaver
#   python3-venv    → afhængighederne holdes for sig selv, se nedenfor
#   openssl         → verificerer signaturen på en ny version (valgfrit, se
#                     "Signeret /opdater" i byggevejledningen)
systemctl enable --now cron 2>/dev/null || true

echo "-- Virtuelt Python-miljø (holder afhængighederne for sig selv)..."
# Tidligere blev python-telegram-bot installeret globalt med
# --break-system-packages. Det flag findes af en grund: Ubuntu beskytter
# systemets egen Python (PEP 668), fordi pip ellers kan overskrive pakker,
# som systemværktøjer afhænger af. Vi brød den beskyttelse, og prisen var
# en fælde med lang lunte: ved en større systemopgradering kan Python
# skifte version, biblioteket forsvinde fra stien — og appen ville ikke
# starte. Rollback ville være magtesløs, for den gendanner appens kode,
# ikke miljøet omkring den.
#
# --system-site-packages er nødvendigt: tkinter og PIL kan ikke installeres
# med pip, de kommer fra apt. Pakker i miljøet vinder over systemets, så
# python-telegram-bot er stadig isoleret.
VENV=/opt/livline/venv
install -d /opt/livline
python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
# --ignore-installed er IKKE overflødigt. Med --system-site-packages ser pip
# også pakker uden for miljøet, og finder den en kopi der, springer den over
# med "Requirement already satisfied" — tilsyneladende uden problemer.
# Miljøet ville så være tomt, og appen ville køre videre på den globale
# pakke, altså præcis det, vi ville væk fra. Det rammer hver eneste maskine,
# hvor python-telegram-bot tidligere blev installeret med
# --break-system-packages. Fanget ved en prøveinstallation, ikke i koden.
"$VENV/bin/pip" install --quiet --ignore-installed "python-telegram-bot>=22,<23"
# ... og så kontrolleres det. En påstand om isolering er ikke isolering.
"$VENV/bin/python" - <<'PYEOF'
import pathlib, sys
import telegram, tkinter, PIL          # noqa: F401 — skal kunne importeres
miljoe = pathlib.Path(sys.prefix).resolve()
sti = pathlib.Path(telegram.__file__).resolve()
if miljoe not in sti.parents:
    raise SystemExit(
        f"FEJL: python-telegram-bot ligger uden for miljøet ({sti}).\n"
        "       Afhængighederne er ikke isolerede — installation afbrudt.")
print(f"   miljø ok: python-telegram-bot {telegram.__version__} i venv")
PYEOF

echo "-- Sikrer bruger og mapper..."
id -u "$KIOSK_USER" &>/dev/null || useradd -m -s /bin/bash "$KIOSK_USER"
usermod -s /bin/bash "$KIOSK_USER"   # grafisk autologin kræver rigtig shell
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" /var/lib/livline /var/lib/livline/media
install -d /opt/livline /etc/livline

echo "-- Kopierer program..."
install -m 755 "$HERE/livline_bot.py" /opt/livline/livline_bot.py
# kiosk-brugeren skal kunne udskifte programmet ved /opdater
chown -R "$KIOSK_USER":"$KIOSK_USER" /opt/livline

# ROOT KØRER ALDRIG NOGET FRA EN MAPPE, KIOSK-BRUGEREN KAN SKRIVE I.
#
# /opt/livline ejes af kiosk-brugeren — det SKAL den, for /opdater
# udskifter livline_bot.py og lægger en .bak ved siden af. Men mappen lå
# før også med de to scripts, root kører fra cron: netcheck.sh hvert
# kvarter og hardware.py hver nat.
#
# Filerne selv var root-ejede, men MAPPEN var ikke. Og den, der må skrive
# i en mappe, må også omdøbe og erstatte filerne i den. Kunne nogen køre
# kode som Livline-brugeren — gennem et billede, der vælter Pillow, eller
# en Python-pakke, der bliver overtaget — kunne de lægge deres egen
# netcheck.sh og have root et kvarter senere.
#
# Derfor bor de to nu her, hvor kun root må skrive:
install -d -o root -g root -m 755 /usr/local/libexec/livline
# Ryd op efter tidligere installationer, så de gamle ikke bliver liggende
# og forvirre den, der leder efter dem.
rm -f /opt/livline/netcheck.sh /opt/livline/hardware.py

echo "-- Syntakstjek..."
"$VENV/bin/python" -m py_compile /opt/livline/livline_bot.py || {
    echo "FEJL: livline_bot.py har en syntaksfejl — installation afbrudt."; exit 1; }

echo "-- Skriver konfiguration..."
# JSON skrives af python, ikke af skallen. Et maskinnavn med anførselstegn
# eller en backslash ("Mor's PC" er harmløst, 'Farmors "Livline"' er ikke)
# ville ellers ødelægge filen — og appen ville ikke starte, uden at det
# stod noget sted, hvorfor.
MACHINE_NAME="$MACHINE_NAME" MODE="$MODE" UPDATE_URL="$UPDATE_URL" \
TOKEN="$TOKEN" ADMIN_ID="$ADMIN_ID" python3 - > /etc/livline/config.json <<'PYEOF'
import json, os
print(json.dumps({
    "token": os.environ["TOKEN"],
    "admin_chat_id": int(os.environ["ADMIN_ID"]),
    "machine_name": os.environ["MACHINE_NAME"],
    "mode": os.environ["MODE"],
    "media_dir": "/var/lib/livline/media",
    "whitelist_path": "/var/lib/livline/whitelist.json",
    "update_url": os.environ["UPDATE_URL"],
}, ensure_ascii=False, indent=4))
PYEOF
python3 -c 'import json,sys; json.load(open("/etc/livline/config.json"))' || {
    echo "FEJL: config.json blev ikke gyldig JSON — installation afbrudt."; exit 1; }
# Bemærk: udseendet (tema, skrift, linjebredde, svarknapper m.m.) sættes i
# programmets standardværdier — ikke her. Så gælder samme udseende for hele
# flåden, og det kan ændres med én gist-opdatering + /opdater.
# Config-filen bruges kun til afvigelser hos den enkelte bruger.
chown root:"$KIOSK_USER" /etc/livline/config.json
chmod 640 /etc/livline/config.json

# Den offentlige nøgle: root-ejet, læsbar for alle. Den er ikke hemmelig
# — den kan kun KONTROLLERE en underskrift, ikke lave en. Men den må kun
# kunne ændres af root: kunne kiosk-brugeren skrive i den, kunne han
# udskifte den med sin egen og dermed godkende sin egen kode.
if [[ -n "$NOEGLEFIL" ]]; then
    install -o root -g root -m 644 "$NOEGLEFIL" /etc/livline/opdater.pub
    echo "   opdater.pub lagt på maskinen — /opdater kræver underskrift ✔"
elif [[ -f /etc/livline/opdater.pub ]]; then
    echo "   opdater.pub lå der i forvejen — beholdt"
else
    echo "   ingen opdater.pub — /opdater er slået fra på denne maskine"
fi

# Tom whitelist ved førstegangsinstallation (familien tilføjes med /tilfoej)
if [[ ! -f /var/lib/livline/whitelist.json ]]; then
    echo '{}' > /var/lib/livline/whitelist.json
    chown "$KIOSK_USER":"$KIOSK_USER" /var/lib/livline/whitelist.json
fi

echo "-- Opretter start-script med auto-genstart..."
cat > /opt/livline/run.sh <<'EOF'
#!/usr/bin/env bash
# KUN ÉN STARTER AD GANGEN. Uden denne lås kunne to run.sh-løkker køre
# samtidig (fx efter manuel start under fejlsøgning). De starter hver sin
# kopi af appen, Telegram tillader kun én forbindelse, kopierne skubber
# hinanden af og dør hurtigt — og rollback-tælleren tolker det som en
# defekt ny version og ruller tilbage uden grund.
exec 9>/run/lock/livline.lock 2>/dev/null || exec 9>/tmp/livline.lock
if ! flock -n 9; then
    echo "Livline: en starter kører allerede — afslutter" | logger -t livline
    exit 0
fi
# VENT PÅ, AT SKRIVEBORDET ER FÆRDIGT MED AT STARTE.
#
# Set i drift to gange: appen kørte, men skærmen viste Ubuntu-logoet.
# Logoet er ikke et vindue — det er Plymouth, som tegner direkte på
# skærmen under opstarten. Vinduesvagten kan derfor ikke lægge sig foran
# det, uanset hvor mange gange den prøver: den flytter vinduer, og et
# opstartsbillede er ikke et vindue.
#
# Starter appen, før GNOME er færdig, bygger den sit vindue ind i en
# session, der endnu ikke tegner. Løsningen er ikke at kæmpe hurtigere,
# men at lade være med at starte kapløbet: vent til gnome-shell kører,
# og giv den så et par sekunder til at falde på plads.
#
# Prisen er nul. Maskinen starter kl. 07:59, og ingen sidder og venter.
for _ in $(seq 1 40); do
    pgrep -x gnome-shell >/dev/null 2>&1 && break
    sleep 1
done
sleep 5
logger -t livline "Skrivebordet er klar — starter Livline"

# Kiosk-indstillinger (kører i den grafiske session — virker på Wayland)
gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null || true
gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null || true
gsettings set org.gnome.settings-daemon.plugins.power \
    sleep-inactive-ac-type 'nothing' 2>/dev/null || true
# ... OG på batteri. Set i drift: da strømmen blev taget for at afprøve
# genstart efter strømsvigt, skiftede maskinen til batteri, og så gjaldt
# skrivebordets BATTERIREGLER i stedet. Den gik i dvale — sort skærm,
# lysende tændknap — og lignede en slukket maskine.
#
# Det værste ved det: en sovende maskine bliver hverken tændt af
# "Power On with AC Attach" eller af urets alarm. Et kort strømsvigt hos
# en familie kunne altså lægge skærmen død, indtil nogen trykkede på en
# tast — og det er præcis den situation, ingen af dem opdager.
gsettings set org.gnome.settings-daemon.plugins.power \
    sleep-inactive-battery-type 'nothing' 2>/dev/null || true
gsettings set org.gnome.settings-daemon.plugins.power \
    sleep-inactive-battery-timeout 0 2>/dev/null || true
gsettings set org.gnome.settings-daemon.plugins.power \
    power-button-action 'nothing' 2>/dev/null || true

# LYSSENSOREN SKAL VÆRE SLÅET FRA — og kun den.
#
# T470s har en lysføler ved skærmen. Med den tændt følger lysstyrken
# rummets lys, uafhængigt af om nogen rører maskinen. Og Livline skriver
# selv en fast lysstyrke ("lysstyrke" i config). To, der skriver i den
# samme fil, giver et lys, der vandrer.
#
# DE TRE ANDRE ER FJERNET IGEN (04.10), og det er værd at læse hvorfor.
#
# Vi slog også idle-dim, idle-activation og night-light fra. Begrundelsen
# var den samme observation: lysstyrken varierede. Den observation var
# rigtig — GNOME dæmpede til 30 %, mens appen skrev fuld styrke tilbage
# hvert halve minut.
#
# Men rettelsen var forkert. Da GNOME ikke længere måtte dæmpe, SLUKKEDE
# et lag længere nede panelet i stedet — helt, hvert 15. sekund. Vi
# byttede en dæmpning, ingen bemærkede, for et blink, alle kunne se.
#
# Målt på maskine 04 den 04.10: med de tre sat tilbage til Ubuntus
# standard blev skærmen tændt i timevis, og GNOME dæmpede pænt til 30 %.
# Med dem slået fra skiftede bl_power mellem 0 og 4 hvert 15. sekund.
#
# Den rigtige løsning står nedenfor: appen beder sessionen om ikke at gå
# i dvale. Så dæmper GNOME aldrig, slukker aldrig — og der er ingen at
# slås med. At fjerne nogens indstillinger er ikke det samme som at
# overtage arbejdet.
gsettings set org.gnome.settings-daemon.plugins.power \
    ambient-enabled false 2>/dev/null || true

gsettings set org.gnome.desktop.notifications show-banners false 2>/dev/null || true
# GENVEJSTASTERNE SLÅS FRA. Set på hardware: et tryk på Windows-tasten
# åbner GNOME's aktivitetsoversigt, og så står skrivebordet foran appen.
# Vinduesvagten henter den tilbage, men der går op til 30 sekunder — og i
# mellemtiden sidder brugeren og kigger på noget helt andet, som hun ikke
# selv kan komme væk fra.
#
# Pointen er ikke at FANGE fejlen. Det er, at den ikke kan laves: en
# maskine, der fanger fejlen, kræver, at brugeren opdager, at noget gik
# galt. En maskine, hvor fejlen ikke kan laves, kræver ingenting.
gsettings set org.gnome.mutter overlay-key '' 2>/dev/null || true
gsettings set org.gnome.shell.keybindings toggle-overview "[]" 2>/dev/null || true
gsettings set org.gnome.desktop.wm.keybindings switch-applications "[]" 2>/dev/null || true
gsettings set org.gnome.desktop.wm.keybindings switch-windows "[]" 2>/dev/null || true
gsettings set org.gnome.desktop.wm.keybindings close "[]" 2>/dev/null || true
gsettings set org.gnome.desktop.wm.keybindings panel-run-dialog "[]" 2>/dev/null || true
gsettings set org.gnome.settings-daemon.plugins.media-keys terminal "[]" 2>/dev/null || true
# Hot corner fra: markør i øverste hjørne må ikke åbne aktivitetsoversigten
gsettings set org.gnome.desktop.interface enable-hot-corners false 2>/dev/null || true
# Lydniveau-kalibrering: fast, hørbart niveau ved hver opstart
pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null || true
pactl set-sink-volume @DEFAULT_SINK@ 75% 2>/dev/null || true
# Kør terminalen — genstart automatisk hvis den lukker/fejler.
# Rollback: dør programmet 3 gange i træk inden for 20 sek. (fx efter en
# fejlslagen /opdater), gendannes den seneste fungerende version (.bak).
# Appen køres med miljøets egen python — ikke systemets. Bruges "python3"
# her, starter appen ikke, for python-telegram-bot ligger kun i miljøet.
LIVLINE_PY=/opt/livline/venv/bin/python
[ -x "$LIVLINE_PY" ] || LIVLINE_PY=/usr/bin/python3   # nødspor: gammel maskine
# APPENS UDSKRIFT SKAL I JOURNALEN.
#
# Her stod før bare programmet, uden omdirigering. Alt, hvad det skrev —
# hver modtaget besked, hver fejlet afsendelse — gik til autostartens
# udskrift, og den samler skrivebordet ikke op. Den forsvandt.
#
# Fundet, da en kvittering kun nåede den ene af to telefoner: fejlen
# skrives med log.warning, og der var ingen log at læse den i. Samme
# mønster som baglyset, der aldrig virkede, fordi fejlen lå i log.debug.
#
# Det ramte også /status, som aflæser "journalctl -t livline" for at se,
# hvornår Telegram sidst svarede. Den oplysning har aldrig været sand.
#
# PYTHONUNBUFFERED, fordi Python ellers gemmer udskriften i en buffer, når
# den ikke skriver til en skærm — og så kommer linjerne først, når appen
# dør. Netop dér, hvor man har mest brug for dem.
export PYTHONUNBUFFERED=1
# SESSIONEN MÅ ALDRIG GÅ I DVALE, MENS LIVLINE KØRER.
#
# Det her er rettelsen på fire dages jagt, og den er værd at forstå.
#
# GNOME dæmper skærmen, når ingen rører maskinen, og slukker den til
# sidst. For en maskine, der står i en stue og SKAL kunne læses på
# afstand uden at nogen rører den, er det forkert — men det er ikke
# GNOME, der tager fejl. Det er os, der ikke har sagt, hvad maskinen er.
#
# Vi prøvede først at slå GNOME's indstillinger fra. Det gav et blink
# hvert 15. sekund, fordi et lag længere nede overtog og slukkede
# panelet helt. Vi fjernede styringen uden at overtage arbejdet.
#
# gnome-session-inhibit holder en "jeg er i gang"-markering, så længe
# kommandoen kører — præcis som en videoafspiller gør under en film.
# Dør appen, forsvinder markeringen af sig selv. Der er ingen tilstand
# at rydde op i, og ingen indstilling at glemme at sætte tilbage.
#
# Findes værktøjet ikke (en maskine uden GNOME), kører appen som før.
# Så dæmper skærmen måske — men maskinen virker, og det siges i loggen.
if command -v gnome-session-inhibit >/dev/null 2>&1; then
    # --inhibit tager EN liste, ikke flere tilvalg. "--inhibit-logout"
    # findes ikke, og med den stod maskinen og viste skrivebordet, mens
    # run.sh prøvede at starte appen hvert femte sekund i tavshed.
    INHIBIT="gnome-session-inhibit --inhibit idle --reason Livline"
    logger -t livline "Skærmen holdes vågen med gnome-session-inhibit"
else
    INHIBIT=""
    logger -t livline "ADVARSEL: gnome-session-inhibit mangler — skærmen kan dæmpe af sig selv"
fi

FAILS=0
while true; do
    START=$(date +%s)
    if command -v systemd-cat >/dev/null 2>&1; then
        systemd-cat -t livline $INHIBIT "$LIVLINE_PY" /opt/livline/livline_bot.py
    else
        $INHIBIT "$LIVLINE_PY" /opt/livline/livline_bot.py 2>&1 | logger -t livline
    fi
    DUR=$(( $(date +%s) - START ))
    if [ "$DUR" -lt 20 ]; then FAILS=$((FAILS+1)); else FAILS=0; fi
    if [ "$FAILS" -ge 3 ] && [ -f /opt/livline/livline_bot.py.bak ]; then
        echo "Livline: crash-loop — ruller tilbage til .bak" | logger -t livline
        cp /opt/livline/livline_bot.py.bak /opt/livline/livline_bot.py
        # Fortæl administrator det i Telegram — ellers opdages en mislykket
        # opdatering først, når nogen undrer sig over versionsnummeret
        /usr/bin/python3 /opt/livline/rollback-besked.py 2>/dev/null || true
        FAILS=0
    fi
    sleep 5
done
EOF
chmod 755 /opt/livline/run.sh

echo "-- Alarm i Telegram hvis en opdatering ruller tilbage..."
cat > /opt/livline/rollback-besked.py <<'EOF'
#!/usr/bin/env python3
"""Sender en besked til administrator, når run.sh har rullet en fejlet
opdatering tilbage. Kaldes af run.sh; fejler den, sker der intet skadeligt."""
import json, re, urllib.parse, urllib.request

cfg = json.load(open("/etc/livline/config.json"))
kode = open("/opt/livline/livline_bot.py", encoding="utf-8").read()
m = re.search(r'^VERSION\s*=\s*"([^"]+)"', kode, re.M)
tekst = (f"⚠️ {cfg.get('machine_name','Livline')}: den nye version kunne ikke "
         f"starte. Maskinen er rullet tilbage til v{m.group(1) if m else '?'} "
         f"og kører videre.\nSe fejlen med:\n"
         f"journalctl -b | grep -A12 Traceback | tail -30")
data = urllib.parse.urlencode({"chat_id": cfg["admin_chat_id"],
                               "text": tekst}).encode()
urllib.request.urlopen(
    f"https://api.telegram.org/bot{cfg['token']}/sendMessage", data, timeout=15)
EOF
chmod 755 /opt/livline/rollback-besked.py
chown "$KIOSK_USER":"$KIOSK_USER" /opt/livline/rollback-besked.py

echo "-- Sætter autostart op for brugeren $KIOSK_USER..."
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "/home/$KIOSK_USER/.config/autostart"
cat > "/home/$KIOSK_USER/.config/autostart/livline.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Livline
Exec=/opt/livline/run.sh
X-GNOME-Autostart-enabled=true
EOF
chown "$KIOSK_USER":"$KIOSK_USER" "/home/$KIOSK_USER/.config/autostart/livline.desktop"

echo "-- Aktiverer automatisk login (GDM)..."
# Uden autologin kommer skærmen aldrig længere end til login-billedet, og
# ingen af de andre sikkerhedsnet hjælper. Derfor skal det både sættes OG
# kontrolleres — også når linjen allerede stod der i forvejen og pegede på
# en anden bruger. Det er en fejl, ingen opdager før første genstart.
if [[ -f /etc/gdm3/custom.conf ]]; then
    if ! grep -q "^AutomaticLogin=" /etc/gdm3/custom.conf; then
        sed -i "s/^\[daemon\]/[daemon]\nAutomaticLoginEnable=true\nAutomaticLogin=$KIOSK_USER/" \
            /etc/gdm3/custom.conf
    fi
    NUVAERENDE=$(grep -oP '^AutomaticLogin=\K.*' /etc/gdm3/custom.conf || true)
    if [[ "$NUVAERENDE" != "$KIOSK_USER" ]]; then
        # HER STOD FØR EN ADVARSEL, OG SÅ KØRTE SCRIPTET VIDERE TIL "Færdig".
        #
        # Pegede GDM på en anden bruger, ville skærmen stå tom efter
        # genstarten — og sluttteksten sagde alligevel, at maskinen logger
        # selv ind og starter Livline. En tilstand, der GARANTERET
        # forhindrer opstart, må ikke være en advarsel, man kan overse
        # klokken elleve om aftenen.
        #
        # Nu rettes den. Med en kopi af filen først, så den kan lægges
        # tilbage, hvis noget går galt.
        echo "   GDM logger ind som '$NUVAERENDE' — retter til '$KIOSK_USER'"
        cp -a /etc/gdm3/custom.conf "/etc/gdm3/custom.conf.livline-$(date +%Y%m%d%H%M%S)"
        sed -i "s/^AutomaticLogin=.*/AutomaticLogin=$KIOSK_USER/" \
            /etc/gdm3/custom.conf
        sed -i "s/^AutomaticLoginEnable=.*/AutomaticLoginEnable=true/" \
            /etc/gdm3/custom.conf
        grep -q "^AutomaticLoginEnable=" /etc/gdm3/custom.conf || \
            sed -i "s/^\[daemon\]/[daemon]\nAutomaticLoginEnable=true/" \
                /etc/gdm3/custom.conf
        EFTER=$(grep -oP '^AutomaticLogin=\K.*' /etc/gdm3/custom.conf || true)
        if [[ "$EFTER" != "$KIOSK_USER" ]]; then
            echo "FEJL: autologin kunne ikke sættes til '$KIOSK_USER'."
            echo "Maskinen ville stå med en tom skærm efter genstart, og det"
            echo "kan ikke rettes over Tailscale. Ret /etc/gdm3/custom.conf"
            echo "i hånden, og kør installationen igen."
            exit 1
        fi
        echo "   autologin rettet til $KIOSK_USER ✔"
    else
        echo "   autologin som $KIOSK_USER ✔"
    fi
else
    # Uden GDM-konfiguration kommer skærmen aldrig forbi login-billedet.
    # Det er ikke en advarsel værd — det er en installation, der ikke kan
    # lykkes, og den skal stoppe, mens du står ved maskinen.
    echo "FEJL: /etc/gdm3/custom.conf findes ikke — autologin kan ikke sættes op."
    echo "Uden autologin står skærmen på login-billedet efter genstart, og"
    echo "Livline starter aldrig. Er GDM installeret? (Ubuntu Desktop, ikke Server)"
    exit 1
fi

echo "-- Skærmen må ikke blinke: Intels panel self-refresh slås fra..."
# SET PÅ MASKINE 02 (28.09), DAGEN FØR DEN SKULLE LEVERES.
#
# Skærmen blev kortvarigt mørk med tilfældige mellemrum. Panel self-refresh
# lader panelet genbruge sit eget billede for at spare strøm, og på flere
# Intel-paneler giver det korte udfald.
#
# På en maskine, der altid står i stikket, sparer den ingenting af værdi.
# Og i en stue er en skærm, der blinker, ikke en skønhedsfejl: den ser ud
# som en maskine på vej i stykker. Familien kan ikke vurdere det, og en
# mand med demens kan slet ikke. Han kan bare se, at noget er galt.
#
# Kun hvis den ikke står der i forvejen — scriptet skal kunne køres igen.
if ! grep -q "i915.enable_psr=0" /etc/default/grub 2>/dev/null; then
    sed -i 's/^\(GRUB_CMDLINE_LINUX_DEFAULT="[^"]*\)"/\1 i915.enable_psr=0"/' \
        /etc/default/grub
    if grep -q "i915.enable_psr=0" /etc/default/grub; then
        update-grub >/dev/null 2>&1 \
            && echo "   panel self-refresh slået fra (virker efter genstart) ✔" \
            || echo "   ADVARSEL: update-grub fejlede — skærmen kan stadig blinke"
    else
        echo "   ADVARSEL: kunne ikke skrive i /etc/default/grub."
        echo "   Blinker skærmen, så tilføj i915.enable_psr=0 til"
        echo "   GRUB_CMDLINE_LINUX_DEFAULT og kør update-grub."
    fi
else
    echo "   panel self-refresh var allerede slået fra ✔"
fi

echo "-- Ladegrænse: batteriet er maskinens nødstrøm og skal holde i årevis..."
# MASKINEN STÅR I STIKKONTAKTEN DØGNET RUNDT, ÅRET RUNDT.
#
# Et litium-batteri, der holdes på 100 %, slides markant hurtigere end et,
# der holdes omkring 80. Og batteriet er ikke en bekvemmelighed her — det
# er det eneste, der holder Livline i live, når strømmen går i en stue.
#
# Målt på to maskiner efter nogle måneder i stikket: 01 er nede på 66 %
# af oprindelig kapacitet, 02 på 78 %. De tal falder videre, så længe de
# lader til fuld.
#
# 80 % af et sundt batteri er mere værd end 100 % af et slidt.
#
# IKKE TLP. Det er en hel strømstyringspakke, der også bestemmer over
# WiFi-strømsparing, USB og diske — og dem har vi allerede sat selv. To
# systemer, der styrer det samme, er præcis det, der kostede en dag på
# lysstyrken. Kernen kan sætte grænsen direkte; det er ét tal i én fil.
install -d -o root -g root -m 755 /usr/local/libexec/livline
cat > /usr/local/libexec/livline/batterigraense.sh <<'BATEOF'
#!/usr/bin/env bash
# Sætter ladegrænsen igen ved hver opstart — værdierne overlever ikke
# en genstart af sig selv.
START=75
SLUT=80
fundet=0
for b in /sys/class/power_supply/BAT*; do
    [ -e "$b/charge_control_end_threshold" ] || continue
    # SLUT skrives FØRST. Flere ThinkPad-firmwares afviser en start-værdi,
    # der ligger over den nuværende slut-værdi.
    if echo "$SLUT" > "$b/charge_control_end_threshold" 2>/dev/null; then
        fundet=1
        if [ -e "$b/charge_control_start_threshold" ]; then
            echo "$START" > "$b/charge_control_start_threshold" 2>/dev/null || true
        fi
        logger -t livline "Ladegrænse sat på $(basename "$b"): $START-$SLUT %"
    fi
done
if [ "$fundet" -eq 0 ]; then
    # IKKE EN FEJL, MEN DET SKAL SIGES. Maskinen virker fint uden; den
    # slider bare batteriet hurtigere. En tavs manglende funktion ville
    # først vise sig som et dødt batteri om to år.
    logger -t livline "ADVARSEL: maskinen understøtter ikke ladegrænse — batteriet lader til 100 %"
fi
# SLUT MED 0, UANSET HVAD.
#
# Første udgave sluttede med  [ "$fundet" -eq 0 ] && logger ...
# Lykkedes alt, var testen falsk, linjen returnerede 1, og det var
# scriptets sidste kommando — så systemd meldte, at tjenesten FEJLEDE,
# mens ladegrænsen stod helt rigtigt på 80.
#
# Det er den værste slags: en tjeneste, der ser defekt ud, mens den gør
# sit arbejde. Kigger man på en maskine og ser rødt på noget, der virker,
# holder man op med at tro på de røde ting.
exit 0
BATEOF
chown root:root /usr/local/libexec/livline/batterigraense.sh
chmod 755 /usr/local/libexec/livline/batterigraense.sh

cat > /etc/systemd/system/livline-batteri.service <<'EOF'
[Unit]
Description=Livline: ladegraense, saa batteriet holder i aarevis
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/libexec/livline/batterigraense.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now livline-batteri.service >/dev/null 2>&1 || true
# Kontrollér at det FAKTISK blev sat. En grænse, der er skrevet i en fil,
# men aldrig nåede hardwaren, ser ud som om problemet var løst.
BATGR=""
for b in /sys/class/power_supply/BAT*; do
    [ -e "$b/charge_control_end_threshold" ] || continue
    BATGR=$(cat "$b/charge_control_end_threshold" 2>/dev/null || true)
    break
done
if [[ "$BATGR" == "80" ]]; then
    echo "   ladegrænse sat til 75-80 % ✔"
elif [[ -z "$BATGR" ]]; then
    echo "   maskinen understøtter ikke ladegrænse — batteriet lader til 100 %."
    echo "   Ikke en fejl, men batteriet slides hurtigere. Noter det på maskinen."
else
    echo "   ADVARSEL: ladegrænsen står på $BATGR, ikke 80. Undersøg med:"
    echo "   systemctl status livline-batteri.service"
fi

echo "-- Låg-lukning: maskinen kører videre (aldrig offline)..."
# STABILITET FØR ALT: låget ignoreres, så maskinen aldrig går offline, og
# der ikke køres dvale/opvågnings-cyklusser (en klassisk kilde til WiFi- og
# driverfejl på bærbare). Ingen vagthund til skærmen: et forsøg med chvt
# blev fravalgt, fordi konsolskift under en kørende Wayland-session selv
# kan forstyrre visningen. Sker det sjældne, at panelet ikke tænder efter
# en låg-lukning, klarer en almindelig genstart det — se byggevejledningen.
install -d /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/livline.conf <<'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
EOF

# MASKINEN MÅ ALDRIG SOVE — heller ikke hvis en indstilling bliver ændret.
# gsettings i run.sh dækker skrivebordet, men de indstillinger kan
# overskrives af en opdatering, en profil eller et uheld. Her lukkes vejen
# i systemd i stedet, og så er der ikke noget lag tilbage, der kan gøre det.
#
# Grunden: en sovende maskine bliver hverken tændt af "Power On with AC
# Attach" eller af urets alarm. Dvale er derfor den eneste tilstand, hvor
# ingen af vores sikkerhedsnet virker.
systemctl mask sleep.target suspend.target hibernate.target \
    hybrid-sleep.target 2>/dev/null || true

# (Ingen skærm-vagthund: se begrundelsen ovenfor — færre bevægelige dele.)
# Rydder en tidligere version af vagthunden, hvis den har været installeret:
systemctl disable --now livline-lid.service 2>/dev/null || true
rm -f /etc/systemd/system/livline-lid.service /opt/livline/lid-watch.sh
systemctl daemon-reload

echo "-- WiFi må ikke gå i strømsparetilstand..."
cat > /etc/NetworkManager/conf.d/livline-wifi.conf <<'EOF'
[connection]
wifi.powersave = 2
EOF

echo "-- Netværks-vagthund (genstarter WiFi ved vedvarende udfald)..."
cat > /usr/local/libexec/livline/netcheck.sh <<'EOF'
#!/usr/bin/env bash
# Kører hvert 15. min via /etc/cron.d/livline-net.
# Genstarter NetworkManager, hvis internettet er væk ved to tjek i træk
# (nogle WiFi-drivere vågner aldrig selv af strømsparetilstand).
STATE=/run/livline-netfail
if ping -c 2 -W 5 8.8.8.8 >/dev/null 2>&1; then rm -f "$STATE"; exit 0; fi
if [ -f "$STATE" ]; then
    systemctl restart NetworkManager
    logger -t livline "Netværk nede ved to tjek i træk — NetworkManager genstartet"
    rm -f "$STATE"
else
    touch "$STATE"
fi
EOF
chown root:root /usr/local/libexec/livline/netcheck.sh
chmod 755 /usr/local/libexec/livline/netcheck.sh
echo "*/15 * * * * root /usr/local/libexec/livline/netcheck.sh" \
    > /etc/cron.d/livline-net

echo "-- Natterytme: maskinen slukker IKKE, den genstarter..."
# MASKINEN SLUKKER IKKE LÆNGERE.
#
# Tidligere slukkede den kl. 22 og skulle vækkes af urets alarm kl. 07:59
# via rtcwake. Prøvet på hardware: maskinen kunne slet ikke vækkes af uret
# — den lå slukket hele den følgende dag, og "Wake Up on Alarm" fandtes
# ikke i BIOS på modellen. Vi kan ikke regne med, at en genbrugt maskine
# kan vågne, og vi kan ikke vælge hardware efter det.
#
# En maskine, der KØRER, kan derimod genstarte sig selv. Så:
#   * skærmen bliver sort 22-08, tegnet af appen selv
#   * maskinen kører videre og modtager beskeder hele natten
#   * genstart kl. 03 giver den friske start, nedlukningen skulle give
#
# Væk er: livline-sengetid, nattevagten, rtcwake og hele afhængigheden af
# BIOS. Tre bevægelige dele færre.
rm -f /usr/local/sbin/livline-sengetid /etc/cron.d/livline-nat
cat > /etc/cron.d/livline-genstart <<'EOF'
0 3 * * * root /sbin/shutdown -r now
EOF
chmod 644 /etc/cron.d/livline-genstart

echo "-- Dagligt hardware-tjek (batteri + disk) til heartbeat..."
cat > /usr/local/libexec/livline/hardware.py <<'EOF'
#!/usr/bin/env python3
"""Skriver batteriets restkapacitet og diskens SMART-status til en fil,
som appen læser og sender med i /status og heartbeat. Kører som root via
cron, så appen selv slipper for særlige rettigheder."""
import json, pathlib, subprocess

ud = {"batteri": None, "disk_smart": None, "opdateringer": None}

# Antal pakker, der venter på en fuld opgradering. Sikkerhedsopdateringer
# installeres automatisk; det her er dem, du selv beslutter (kvartalsvis).
try:
    r = subprocess.run(["apt-get", "-s", "upgrade"],
                       capture_output=True, text=True, timeout=120,
                       env={"DEBIAN_FRONTEND": "noninteractive", "LANG": "C",
                            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"})
    for linje in r.stdout.splitlines():
        if linje.endswith("not upgraded.") or " upgraded, " in linje:
            ud["opdateringer"] = int(linje.split()[0])
            break
except Exception:
    pass

# Flere ThinkPads har to batterier (internt + udtageligt). Rapportér det
# DÅRLIGSTE — det er dét, der først bliver et problem.
for bat in pathlib.Path("/sys/class/power_supply").glob("BAT*"):
    for felt in ("energy", "charge"):   # maskiner bruger det ene eller andet
        try:
            nu = int((bat / f"{felt}_full").read_text())
            design = int((bat / f"{felt}_full_design").read_text())
            pct = round(100 * nu / design)
            if ud["batteri"] is None or pct < ud["batteri"]:
                ud["batteri"] = pct
            break
        except Exception:
            continue

# Find diskene automatisk i stedet for faste navne — så virker tjekket
# også på eMMC (mmcblk0) og maskiner med flere eller anderledes diske
diske = []
try:
    r = subprocess.run(["lsblk", "-dno", "NAME,TYPE"],
                       capture_output=True, text=True, timeout=15)
    diske = ["/dev/" + l.split()[0] for l in r.stdout.splitlines()
             if l.strip().endswith("disk")]
except Exception:
    diske = ["/dev/nvme0n1", "/dev/sda"]

for disk in diske:
    try:
        r = subprocess.run(["smartctl", "-H", disk],
                           capture_output=True, text=True, timeout=30)
        for linje in r.stdout.splitlines():
            if "overall-health" in linje or "SMART Health Status" in linje:
                ud["disk_smart"] = linje.split(":")[-1].strip()
                break
        if ud["disk_smart"] and ud["disk_smart"] != "PASSED":
            break        # en fejlende disk vejer tungest — meld den
    except Exception:
        pass

sti = pathlib.Path("/var/lib/livline/hardware.json")
sti.write_text(json.dumps(ud), encoding="utf-8")
EOF
chown root:root /usr/local/libexec/livline/hardware.py
chmod 755 /usr/local/libexec/livline/hardware.py
echo "40 3 * * * root /usr/bin/python3 /usr/local/libexec/livline/hardware.py" \
    > /etc/cron.d/livline-hardware
/usr/bin/python3 /usr/local/libexec/livline/hardware.py 2>/dev/null || true

echo "-- Baggrundslys: kiosk-brugeren skal kunne slukke det..."
# FUNDET PÅ HARDWARE, I ET MØRKT RUM: appen havde aldrig kunnet skrue lyset
# ned. /sys/class/backlight/*/brightness ejes af root, appen kører som
# kiosk-brugeren, og skrivningen fejlede hver eneste gang — men fejlen blev
# slugt af en log.debug. Skærmen stod på 313 af 1023 hele natten, mens alt
# så rigtigt ud i loggen.
#
# Reglen kører ved hver opstart, fordi filerne laves på ny af kernen.
cat > /etc/udev/rules.d/90-livline-baglys.rules <<'EOF'
ACTION=="add", SUBSYSTEM=="backlight", RUN+="/bin/chgrp video /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"
ACTION=="add", SUBSYSTEM=="backlight", RUN+="/bin/chmod g+w /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"
EOF
usermod -aG video "$KIOSK_USER"
# Sæt rettighederne med det samme, så de gælder uden en genstart
for d in /sys/class/backlight/*/; do
    for f in brightness bl_power; do
        #   bl_power manglede her. Udev-reglen tog begge filer, men den
        #   kører først ved næste opstart — og bl_power er netop den, der
        #   gør skærmen HELT mørk. Lysstyrken kan skrues ned; kun bl_power
        #   slukker panelet.
        [ -e "$d$f" ] || continue
        chgrp video "$d$f" 2>/dev/null || true
        chmod g+w  "$d$f" 2>/dev/null || true
    done
done
# KONTROLLÉR DET — VED AT GØRE DET.
#
# Her stod før "sudo -u $KIOSK_USER test -w". Den spurgte om lov, og fik
# nej — mens en RIGTIG skrivning som samme bruger lykkedes uden videre.
# De to var uenige, og kontrollen advarede på hver eneste installation.
#
# En advarsel, der råber uden grund, er værre end ingen advarsel: den
# lærer én at overse advarsler. Da den rigtige fejl kom (baglyset virkede
# faktisk ikke, i månedsvis), stod den i en log, ingen læste.
#
# Så vi prøver det, vi er interesserede i: kan appen slukke skærmen.
# Den nuværende værdi skrives tilbage til sig selv — ingen synlig ændring,
# men en ægte skrivning. Mål det, der betyder noget, ikke noget der ligner.
for d in /sys/class/backlight/*/; do
    [ -e "$d/brightness" ] || continue
    for f in brightness bl_power; do
        [ -e "$d$f" ] || continue
        vaerdi=$(cat "$d$f" 2>/dev/null) || continue
        if sudo -u "$KIOSK_USER" bash -c "echo '$vaerdi' > '$d$f'" 2>/dev/null; then
            echo "   OK: $KIOSK_USER kan skrive til $f"
        else
            echo "   ADVARSEL: $KIOSK_USER kan IKKE skrive til $d$f."
            if [[ "$f" == "bl_power" ]]; then
                echo "             Skærmen kan ikke slukkes helt — den vil lyse"
                echo "             svagt hele natten i et soveværelse."
            else
                echo "             Lysstyrken kan ikke skrues ned om natten."
            fi
            echo "             Prøv igen efter en genstart, hvor udev-reglen har kørt."
        fi
    done
done

echo "-- livline-wifi: læg et netværk ind uden at koden havner i historikken..."
cat > /usr/local/bin/livline-wifi <<'WIFIEOF'
#!/usr/bin/env bash
# Lægger et WiFi ind på maskinen — eller viser dem, der allerede er.
#
# KODEN TASTES. DEN SKAL IKKE STÅ I EN KOMMANDO, DU SELV SKRIVER.
# En kode, DU taster på kommandolinjen, havner i ~/.bash_history og ville
# blive liggende i årevis på en maskine i en fremmed stue. Det var nær
# sket én gang; derfor findes denne fil.
#
# ÆRLIGT OM GRÆNSEN: koden gives videre til nmcli som et argument, og i
# det sekund kommandoen kører, kan den ses i maskinens proces-liste af en,
# der kigger samtidig. Historikken rører den ikke, og filen gemmer den
# ikke. Fundet ved gennemgangen 28.09: den gamle kommentar her sagde
# "aldrig som argument", og det passede ikke. En kommentar, der lover for
# meget, er farligere end ingen kommentar — man holder op med at tænke
# over det, den dækker over.
#
# Nettet behøver IKKE være i nærheden. Familiens WiFi kan lægges ind,
# mens maskinen står på dit eget bord — og det er sådan, det skal gøres:
# der laves ikke teknik i stuen.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Kør med sudo."; exit 1; fi

# ---------------------------------------------------------------- kodefelt
# EN PROMPT, DER IKKE VISER NOGET, LIGNER EN MASKINE, DER HAR HÆNGT SIG.
#
# Prøvet på maskine 02 med et USB-tastatur (29.09): "read -rsp" viser
# intet overhovedet — ikke engang at markøren flytter sig. Man taster en
# lang kode ud i ingenting og trykker Enter for at se, om maskinen lever.
# I en fremmed stue, med nogen der kigger, er det ikke rart.
#
# Nu kommer der en stjerne pr. tegn. Koden kan stadig ikke læses over
# skulderen, men man kan SE, at maskinen tager imod. Backspace virker.
laes_kode() {
    local svar="" tegn
    printf '%s' "$1" >&2
    while IFS= read -rsn1 tegn; do
        [[ -z "$tegn" ]] && break                 # Enter
        if [[ "$tegn" == $'\177' || "$tegn" == $'\b' ]]; then
            if [[ -n "$svar" ]]; then
                svar="${svar%?}"; printf '\b \b' >&2
            fi
        else
            svar+="$tegn"; printf '*' >&2
        fi
    done
    printf '\n' >&2
    printf '%s' "$svar"
}

# SKIFT MED EN SNOR I. Bruges både af --skift og af spørgsmålene
# nedenfor, så der kun findes ÉN måde at skifte net på — og dermed kun
# ét sted, fortrydelsen kan blive glemt.
skift_til() {
    local NYT="$1" GAMMELT
    GAMMELT=$(nmcli -t -f NAME,TYPE connection show --active 2>/dev/null \
              | awk -F: '$2=="802-11-wireless"{print $1; exit}')
    if [[ -z "$GAMMELT" ]]; then
        echo "FEJL: maskinen står ikke på et WiFi lige nu — kan ikke fortryde."
        echo "      Skift i stedet i hånden med nmcli."
        return 1
    fi
    if [[ "$GAMMELT" == "$NYT" ]]; then
        echo "Maskinen står allerede på \"$NYT\". Intet ændret."
        return 0
    fi
    systemctl stop livline-fortryd.timer 2>/dev/null || true
    if ! systemd-run --unit=livline-fortryd --on-active=300 \
         --description="Livline: saetter nettet tilbage, hvis skiftet ikke virkede" \
         nmcli connection up "$GAMMELT" >/dev/null 2>&1; then
        echo "FEJL: kunne ikke bestille en fortrydelse. Skifter IKKE."
        echo "      Uden den kan maskinen ende uden for rækkevidde."
        return 1
    fi
    echo
    echo "Fortrydelse bestilt: om 5 minutter går maskinen tilbage til"
    echo "\"$GAMMELT\", medmindre du siger til."
    echo
    echo "Skifter nu til \"$NYT\" — forbindelsen ryger et øjeblik."
    echo
    echo "VIRKER DET? Så log ind igen og kør:"
    echo "   sudo livline-wifi --behold"
    echo
    nmcli connection up "$NYT" || true
    return 0
}

vis_gemte() {
    echo "Gemte net (maskinen vælger selv det, der er i nærheden):"
    nmcli -g NAME,TYPE connection show 2>/dev/null \
        | awk -F: '$2=="802-11-wireless"{print "   " $1}'
}

# SKIFT NET PÅ AFSTAND — MED EN SNOR I.
#
# Familien skifter router om to år. Uden det her skal du køre derud.
#
# Men et netskifte river fjernforbindelsen væk i samme sekund, og virker
# det nye net ikke, er maskinen uden for rækkevidde. Derfor bestilles en
# FORTRYDELSE, før der skiftes: om fem minutter sætter maskinen sig selv
# tilbage på det gamle net, medmindre du når at sige, at det nye virker.
#
# Samme regel som alt andet her: du må ikke kunne låse dig selv ude.
if [[ $# -ge 1 && "$1" == "--behold" ]]; then
    if systemctl stop livline-fortryd.timer 2>/dev/null; then
        echo "Fortrydelsen er aflyst. Maskinen bliver på det net, den står på."
    else
        echo "Der var ingen fortrydelse at aflyse — intet ændret."
    fi
    exit 0
fi

if [[ $# -ge 1 && "$1" == "--skift" ]]; then
    [[ $# -ge 2 ]] || { echo "Brug: sudo livline-wifi --skift \"navn\""; exit 1; }
    if ! nmcli -g NAME connection show 2>/dev/null | grep -qxF "$2"; then
        echo "FEJL: \"$2\" er ikke lagt ind endnu."
        echo "      Læg det ind først med: sudo livline-wifi"
        exit 1
    fi
    skift_til "$2"
    exit $?
fi

if [[ $# -ge 1 && "$1" == "--glem" ]]; then
    [[ $# -ge 2 ]] || { echo "Brug: sudo livline-wifi --glem \"navn\""; exit 1; }
    nmcli connection delete "$2" && echo "Fjernet: $2"
    exit 0
fi

if [[ $# -ge 1 ]]; then
    SSID="$1"
else
    # VÆLG FRA EN LISTE I STEDET FOR AT SKRIVE NAVNET.
    #
    # Familiens netnavn er typisk noget i retning af "FTTH_PP2869" eller
    # "Zyxel-2G-A41B". Det skal tastes rigtigt hver gang, og en enkelt
    # forkert karakter giver et net, maskinen aldrig finder — uden at
    # noget ser forkert ud. Er nettet i nærheden, kan maskinen læse
    # navnet selv, og så skal ingen stave til det.
    vis_gemte
    echo
    echo "Søger efter net i nærheden..."
    mapfile -t FUNDET < <(
        nmcli -t -f SIGNAL,SSID device wifi list --rescan yes 2>/dev/null \
        | awk -F: 'NF>=2 && $2 != ""' \
        | sort -t: -k1 -nr \
        | awk -F: '!set[$2]++ {print $2 "\t" $1}'
    )
    echo
    if (( ${#FUNDET[@]} == 0 )); then
        echo "Ingen net i nærheden. Du kan stadig lægge et ind til senere:"
        echo "   sudo livline-wifi \"Netværkets navn\""
        exit 0
    fi
    for i in "${!FUNDET[@]}"; do
        navn="${FUNDET[$i]%%$'\t'*}"; styrke="${FUNDET[$i]##*$'\t'}"
        printf '  %2d)  %-32s %s%%\n' "$((i+1))" "$navn" "$styrke"
    done
    echo
    echo "Skriv et NUMMER for at vælge, eller skriv navnet på et net, der"
    echo "ikke er i nærheden. Enter afslutter uden at ændre noget."
    read -rp "Valg: " VALG
    if [[ -z "$VALG" ]]; then
        echo "Intet ændret."
        exit 0
    elif [[ "$VALG" =~ ^[0-9]+$ ]]; then
        if (( VALG < 1 || VALG > ${#FUNDET[@]} )); then
            echo "FEJL: der er kun ${#FUNDET[@]} net på listen. Intet ændret."
            exit 1
        fi
        SSID="${FUNDET[$((VALG-1))]%%$'\t'*}"
        echo "Valgt: $SSID"
    else
        SSID="$VALG"
    fi
fi

# ET WIFI-NAVN KAN HØJST VÆRE 32 TEGN. Det er en grænse i standarden, og
# den er gratis at kontrollere.
#
# Set 01.10: en indsætning, der indeholdt mere end den ene linje, endte i
# svarfeltet — og kommandoen begyndte pænt at spørge om koden til et
# "net", der i virkeligheden var en hel kommandolinje. Uden det her tjek
# ville et Enter have oprettet en forbindelse med det navn.
if (( ${#SSID} > 32 )); then
    echo "FEJL: \"${SSID:0:40}…\""
    echo "      Det er ${#SSID} tegn. Et WiFi-navn kan højst være 32."
    echo "      Kom der mere end én linje med, da du satte ind? Prøv igen."
    exit 1
fi
if [[ -z "${SSID// }" ]]; then
    echo "FEJL: tomt netværksnavn. Intet ændret."
    exit 1
fi

# KOBL ALDRIG PÅ MED DET SAMME.
#
# Her stod før en gren, der brugte "nmcli --ask device wifi connect", når
# nettet var i nærheden. Den lod nmcli spørge om koden, så den aldrig rørte
# kommandolinjen — pænt i teorien.
#
# I praksis: maskinen fjernstyres over det net, den står på. Begynder den
# at skifte, ryger SSH-forbindelsen i samme sekund — FØR man når at taste
# koden. Set to gange. Anden gang lod jeg den stå, og den ventede 90
# sekunder på en kode, ingen kunne skrive.
#
# Nu gør kommandoen kun ÉN ting: den lægger nettet ind. Maskinen kobler
# sig selv på, når nettet er det bedste, den kan se — og hos familien er
# det det eneste, der findes.
# KENDES NETTET I FORVEJEN? Så spørg, før koden overskrives.
#
# Vælger man et net fra listen for at se, hvad der sker, gik kommandoen
# før direkte videre til kodefeltet — som om man ville ændre den. En
# tastefejl dér overskriver en kode, der virker, og fejlen viser sig
# først næste gang maskinen skal bruge nettet.
if nmcli -g NAME connection show 2>/dev/null | grep -qxF "$SSID"; then
    echo "\"$SSID\" kender maskinen allerede."
    read -rp "Vil du opdatere koden? [j/N]: " OPDAT
    if [[ ! "$OPDAT" =~ ^[jJyY]$ ]]; then
        echo "Koden er urørt."
        # TILBYD SKIFTET HER. Det var klodset at få besked om at skrive en
        # kommando, man lige har valgt sig frem til.
        read -rp "Skal maskinen skifte til \"$SSID\" nu? [j/N]: " SKIFT
        if [[ "$SKIFT" =~ ^[jJyY]$ ]]; then
            skift_til "$SSID"
            exit $?
        fi
        echo "Intet ændret."
        exit 0
    fi
fi

K1="$(laes_kode "Kode til \"$SSID\" (tom = åbent net): ")"
K2=""
if [[ -n "$K1" ]]; then
    # WPA kræver mindst 8 tegn. Uden dette tjek svarer nmcli
    # "psk: property is invalid", og det siger ingenting om hvorfor.
    if (( ${#K1} < 8 )); then
        echo "FEJL: koden skal være mindst 8 tegn (WPA's krav)."
        echo "      Sæt en længere kode på nettet, og prøv igen."
        exit 1
    fi
    # EN TASTEFEJL HER OPDAGES ELLERS FØRST HOS FAMILIEN, hvor maskinen
    # bare ikke vil koble sig på, og hvor ingen kan se hvorfor.
    #
    # To veje til samme sikkerhed, og du vælger selv:
    #   - se koden én gang og kontrollér den med øjnene
    #   - eller taste den igen
    # At se den er det stærkeste tjek, men gør det kun, når ingen kigger
    # med. Står du i en stue, så tast den hellere to gange.
    read -rp "Vis koden, så du kan kontrollere den? [j/N]: " VIS
    if [[ "$VIS" =~ ^[jJyY]$ ]]; then
        echo "   Koden er: $K1"
        read -rp "Er den rigtig? [j/N]: " OK
        if [[ ! "$OK" =~ ^[jJyY]$ ]]; then
            echo "Intet ændret."
            exit 1
        fi
    else
        K2="$(laes_kode "Skriv den igen: ")"
        if [[ "$K1" != "$K2" ]]; then
            echo "FEJL: de to koder er ikke ens. Intet ændret."
            exit 1
        fi
    fi
fi

if nmcli -g NAME connection show 2>/dev/null | grep -qxF "$SSID"; then
    echo "   \"$SSID\" findes i forvejen — opdaterer koden"
    if [[ -n "$K1" ]]; then
        nmcli connection modify "$SSID" \
            wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$K1"
    else
        nmcli connection modify "$SSID" wifi-sec.key-mgmt none
    fi
elif [[ -n "$K1" ]]; then
    nmcli connection add type wifi con-name "$SSID" ssid "$SSID" \
        wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$K1"
else
    nmcli connection add type wifi con-name "$SSID" ssid "$SSID"
fi
K1=""; K2=""

nmcli connection modify "$SSID" connection.autoconnect yes
echo
echo "Lagt ind: $SSID"
echo "Maskinen kobler sig selv på, når nettet er i nærheden — og når det"
echo "er det eneste, den kan se. Din fjernforbindelse er urørt."
echo
read -rp "Skal maskinen skifte til \"$SSID\" nu? [j/N]: " SKIFT
if [[ "$SKIFT" =~ ^[jJyY]$ ]]; then
    skift_til "$SSID"
fi
exit 0
WIFIEOF
chmod 755 /usr/local/bin/livline-wifi
echo "   livline-wifi lagt på maskinen ✔"

if [[ -n "$NOEDNET" ]]; then
    echo "-- Nødnet: $NOEDNET..."
    # LAVEST MULIG PRIORITET. Nødnettet må ALDRIG vinde over familiens
    # eget net. Gjorde det det, kunne maskinen finde på at skifte, mens
    # alt virkede — og det kostede os fjernforbindelsen to gange i sidste
    # uge. Negativ autoconnect-priority betyder: tages kun, når intet
    # andet er at finde.
    #
    # Der kobles ikke på nu. Samme regel som livline-wifi: et skift af net
    # midt i en installation river SSH-forbindelsen væk.
    if nmcli -g NAME connection show 2>/dev/null | grep -qxF "$NOEDNET"; then
        nmcli connection modify "$NOEDNET" \
            wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$NOEDPSK" || true
    else
        nmcli connection add type wifi con-name "$NOEDNET" ssid "$NOEDNET" \
            wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$NOEDPSK" || true
    fi
    nmcli connection modify "$NOEDNET" connection.autoconnect yes \
        connection.autoconnect-priority -100 || true
    NOEDPSK=""
    # Kontrollér, at den faktisk ligger der. En installation, der SIGER
    # "nødnet lagt ind", men ikke gjorde det, er værre end ingenting:
    # så regner du med det den dag, du står i stuen.
    if nmcli -g NAME connection show 2>/dev/null | grep -qxF "$NOEDNET"; then
        echo "   nødnettet \"$NOEDNET\" lagt ind (laveste prioritet) ✔"
    else
        echo "   ADVARSEL: nødnettet kunne IKKE lægges ind. Læg det ind"
        echo "   manuelt med: livline-wifi \"$NOEDNET\""
    fi
else
    echo "-- Nødnet: sprunget over. Læg det ind senere med livline-wifi."
fi

echo "-- livline-vis: skift mellem de tre opsætninger..."
# Bruges ved levering: prøv alle tre med den ældre siddende foran, og vælg
# ud fra hvad hun FAKTISK gør. Pårørende svarer typisk for optimistisk om,
# hvad deres mor kan — det er svært at sige noget andet højt.
cat > /usr/local/sbin/livline-vis <<'EOF'
#!/usr/bin/env bash
# Skifter mellem de tre opsætninger og genstarter appen.
#
# TAGER BÅDE TAL OG NAVNE. Tallene er de oprindelige og bevares, så gamle
# noter og den trykte vejledning stadig passer. Navnene er til Telegram:
# appens /vis sender navnet HERIND i stedet for at have sin egen tabel.
# Oversættelsen findes derfor ét sted. To steder ville før eller siden
# komme til at betyde noget forskelligt — det er den fejl, der kostede en
# dag på lysstyrken.
set -euo pipefail
case "${1:-}" in
  1|knapper) M=faellestraad; B=knapper  ;;
  2|skriv)   M=faellestraad; B=tastatur ;;
  3|enkelte) M=enkelte;      B=tastatur ;;
  *) echo "Brug: livline-vis 1|2|3  (eller knapper|skriv|enkelte)"
     echo "  1  knapper   faste svar, én fælles samtale"
     echo "  2  skriv     frit skrivefelt, én fælles samtale"
     echo "  3  enkelte   frit skrivefelt, én samtale pr. person"
     echo
     python3 - <<'NUEOF' || true
import json, pathlib
try:
    d = json.loads(pathlib.Path('/etc/livline/config.json').read_text())
    print("Kører nu: %s / %s" % (d.get("mode", "?"),
                                 d.get("betjening", "knapper")))
except Exception as e:
    print("Kunne ikke læse config: %s" % e)
NUEOF
     exit 1 ;;
esac
python3 - "$M" "$B" <<'PYEOF'
# SKRIVER IKKE DIREKTE I CONFIG.JSON. Går strømmen midt i en skrivning,
# ville maskinen stå med en halv JSON-fil og slet ikke kunne starte — og
# det er ikke noget, en pårørende kan rette. Derfor: skriv ved siden af,
# læs filen tilbage som JSON, og først derefter flyt den på plads.
# os.replace er atomisk inden for samme filsystem: enten den gamle eller
# den nye fil, aldrig noget midt imellem.
#
# Rettigheder sættes udtrykkeligt. En ny fil ville ellers arve root:root
# 600 fra umask, og så kunne appen ikke læse sin egen config bagefter.
import json, os, pathlib, sys
p = pathlib.Path('/etc/livline/config.json')
st = p.stat()
d = json.loads(p.read_text())
d["mode"], d["betjening"] = sys.argv[1], sys.argv[2]
t = p.with_suffix('.json.ny')
t.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
os.chown(t, st.st_uid, st.st_gid)
os.chmod(t, st.st_mode & 0o7777)
json.loads(t.read_text())          # vælter her, hvis filen er ufuldstændig
os.replace(t, p)
PYEOF
pkill -f livline_bot.py || true
echo "Opsætning $1 — $M / $B. Skærmen skifter om et par sekunder."
EOF
chmod 755 /usr/local/sbin/livline-vis

# APPEN SKAL KUNNE KØRE livline-vis — OG KUN DEN.
#
# /vis i Telegram skal kunne skifte brugerfladen, uden at der køres ud til
# maskinen. Men config.json er root:KIOSK 640: appen må læse den, ikke
# skrive i den, og det skal den blive ved med. Tokenet står i filen, og en
# app, der kan skrive i sin egen config, kan også ændre update_url.
#
# Derfor den smalle vej: kiosk-brugeren får lov til at køre netop dette
# ene script som root. Kan nogen misbruge appen, kan de skifte
# brugerfladen og genstarte den. De kan ikke læse tokenet bedre end før,
# ikke pege opdateringer et andet sted hen, og ikke fjerne opdater.pub.
#
# visudo -c kontrollerer filen FØR den tages i brug. En ødelagt sudoers-fil
# gør, at INGEN kan bruge sudo på maskinen — heller ikke du, over Tailscale.
echo "-- sudo-adgang til livline-vis for $KIOSK_USER..."
cat > /etc/sudoers.d/livline-vis <<EOF
$KIOSK_USER ALL=(root) NOPASSWD: /usr/local/sbin/livline-vis
EOF
chmod 440 /etc/sudoers.d/livline-vis
if ! visudo -c -f /etc/sudoers.d/livline-vis >/dev/null 2>&1; then
    rm -f /etc/sudoers.d/livline-vis
    echo "FEJL: sudoers-linjen blev ikke gyldig — fjernet igen."
    echo "      /vis virker ikke, men maskinen er uskadt. Resten fortsætter."
fi

echo "-- livline-rapport: maskinens tilstand i én linje (til vagtcentralen)..."
# Ingen bruger den endnu. Den lægges ind NU, fordi den skal ligge på hver
# maskine, den dag en vagtcentral spørger dem — og uden den skal hver
# maskine besøges igen. Den koster ingenting at have med.
#
# VIGTIGT: den udleverer TAL OG TIDSPUNKTER, aldrig indhold. En
# overvågning, der kan læse familiens beskeder, er en anden slags
# overvågning, uanset hvad den bruges til.
cat > /usr/local/bin/livline-rapport <<'EOF'
#!/usr/bin/env python3
"""Skriver maskinens tilstand som én linje JSON. Beregnet til at blive
kaldt udefra over Tailscale SSH:  ssh livline@maskine livline-rapport

Indeholder aldrig beskedtekst — kun tal og tidspunkter."""
import json, pathlib, re, shutil, subprocess, time
from datetime import datetime

ud = {"tid": datetime.now().isoformat(timespec="seconds")}

# Kører programmet, og hvor længe har det kørt?
try:
    r = subprocess.run(["pgrep", "-f", "livline_bot.py"],
                       capture_output=True, text=True, timeout=10)
    pids = [p for p in r.stdout.split() if p]
    ud["koerer"] = bool(pids)
    if pids:
        with open(f"/proc/{pids[0]}/stat") as f:
            start_ticks = int(f.read().split()[21])
        hz = 100.0
        oppe = time.clock_gettime(time.CLOCK_BOOTTIME) - start_ticks / hz
        ud["app_oppetid_sek"] = int(oppe)
except Exception as e:
    ud["koerer"] = None
    ud["fejl_proces"] = str(e)

try:
    ud["version"] = re.search(
        r'^VERSION = "([^"]+)"',
        pathlib.Path("/opt/livline/livline_bot.py").read_text(encoding="utf-8"),
        re.M).group(1)
except Exception:
    ud["version"] = None

# Hvornår svarede Telegram sidst? Aflæses af httpx-linjer i journalen.
try:
    r = subprocess.run(
        ["journalctl", "-b", "-t", "livline", "--no-pager", "-n", "400",
         "-o", "short-iso"], capture_output=True, text=True, timeout=20)
    ud["fejl_i_log"] = sum(1 for l in r.stdout.splitlines()
                           if "ERROR" in l or "Kunne ikke sende" in l)
except Exception:
    ud["fejl_i_log"] = None

# Ubesvarede beskeder: kom ind, men brugeren har ikke kvitteret eller svaret.
# Det er den eneste fejl, der ikke kan ses indefra — maskinen kører jo fint.
try:
    rows = json.loads(pathlib.Path(
        "/var/lib/livline/historik.json").read_text(encoding="utf-8"))
    sidst_egen = {}
    for r_ in rows:
        if r_.get("egen"):
            sidst_egen[str(r_.get("chat_id"))] = r_.get("tid")
    ubesvarede = 0
    nyeste = None
    for r_ in rows:
        if r_.get("egen"):
            continue
        nyeste = max(nyeste or r_["tid"], r_["tid"])
        svar = sidst_egen.get(str(r_.get("chat_id")))
        if svar is None or svar < r_["tid"]:
            alder = datetime.now() - datetime.fromisoformat(r_["tid"])
            if alder.total_seconds() > 86400:
                ubesvarede += 1
    ud["ubesvarede_over_1_doegn"] = ubesvarede
    ud["sidste_besked_ind"] = nyeste
except Exception:
    ud["ubesvarede_over_1_doegn"] = None

du = shutil.disk_usage("/")
ud["disk_fri_gb"] = round(du.free / 1e9, 1)
try:
    ud.update(json.loads(pathlib.Path(
        "/var/lib/livline/hardware.json").read_text(encoding="utf-8")))
except Exception:
    pass
try:
    ud["maskine_oppetid_sek"] = int(float(open("/proc/uptime").read().split()[0]))
except Exception:
    pass

print(json.dumps(ud, ensure_ascii=False))
EOF
chmod 755 /usr/local/bin/livline-rapport
/usr/local/bin/livline-rapport >/dev/null 2>&1 \
    && echo "   livline-rapport svarer ✔" \
    || echo "   ADVARSEL: livline-rapport kunne ikke køre"

echo "-- Medie-oprydning: familiens billeder slettes efter 30 dage..."
# (Beskedhistorikken i historik.json holder sig selv på 100 poster.)
echo "30 20 * * * root find /var/lib/livline/media -type f -mtime +30 -delete" \
    > /etc/cron.d/livline-media

echo "-- Firewall (UFW): afvis alt indgående, tillad Tailscale..."
# NB: Blokerer også SSH fra lokalnettet — al fjernadgang går via Tailscale.
# Reglen for tailscale0 er gyldig, selv om interfacet først findes efter Fase 4.
if command -v ufw >/dev/null; then
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow in on tailscale0 2>/dev/null || true
    ufw --force enable
fi

echo "-- SSH: kun Tailscale-identitet, ingen adgangskoder..."
# Stod tidligere som et manuelt trin i kommandolisten. Et sikkerhedstrin,
# der skal huskes, bliver før eller siden glemt — og netop den maskine,
# hvor det blev glemt, er den, der står hos en familie i årevis.
#
# UFW lukker allerede alt indgående uden for tailnettet, så dette er det
# andet lag: selv med adgang til nettet kan en adgangskode ikke gættes.
if [[ -d /etc/ssh/sshd_config.d ]]; then
    cat > /etc/ssh/sshd_config.d/livline.conf <<'EOF'
# Livline: al fjernadgang går gennem Tailscale-identitet.
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
    if sshd -t 2>/dev/null; then
        systemctl reload ssh 2>/dev/null || systemctl restart ssh 2>/dev/null || true
        echo "   adgangskode-login slået fra ✔"
    else
        # Hellere en maskine, du kan komme ind på, end en du har låst dig ude af
        rm -f /etc/ssh/sshd_config.d/livline.conf
        echo "   ADVARSEL: sshd afviste indstillingen — den er fjernet igen"
    fi
else
    echo "   ADVARSEL: openssh-server ser ikke ud til at være installeret"
fi

echo "-- Silent Guard: stille drift + automatiske sikkerhedsopdateringer..."
apt-get install -y -q unattended-upgrades
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
sed -i 's/^Prompt=.*/Prompt=never/' /etc/update-manager/release-upgrades 2>/dev/null || true
[[ -f /etc/default/apport ]] && sed -i 's/^enabled=.*/enabled=0/' /etc/default/apport
systemctl mask --now cups.service cups.socket cups-browsed.service \
    cups.path 2>/dev/null || true
#   mask, ikke disable: disable holdt ikke. Set på maskine 04 startede cupsd
#   igen af sig selv, og to notifier-processer kørte. Mask lukker døren.

echo "-- Ingen andre programmer må åbne vinduer..."
# DEN VIGTIGSTE SIKRING PÅ HELE MASKINEN.
#
# Set i drift på maskine 04: et vindue lagde sig oven på Livline, og
# skærmen viste Ubuntus skrivebord. Programmet kørte upåklageligt hele
# tiden — appen var ikke død, loggen var ren, og maskinen troede selv,
# at alt var godt.
#
# Vinduesvagten kunne ikke tage forgrunden tilbage. Det kan den ikke på
# Wayland: et vindue, der beder om at komme frem, får lov, og vores
# -topmost bliver ikke altid respekteret. Den kamp kan vi ikke vinde.
#
# Så vi kæmper ikke om forgrunden. Vi sørger for, at der ikke findes
# andre vinduer. Det er den eneste sikring, der holder, og den koster
# ingenting: de her programmer har ingen opgave på en maskine, hvor
# ingen læser notifikationer.
#
# Den, der fandt fejlen, lukkede vinduet med musen. Det kan den, maskinen
# er bygget til, ikke. For ham ville skærmen bare være holdt op med at
# virke — og han ville ikke kunne sige hvorfor.
AUTOSTART="/home/$KIOSK_USER/.config/autostart"
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" "$AUTOSTART"
for d in update-notifier \
         ubuntu-advantage-notification \
         ubuntu-report-on-upgrade \
         org.gnome.Evolution-alarm-notify \
         org.gnome.SettingsDaemon.DiskUtilityNotify \
         orca-autostart \
         geoclue-demo-agent \
         spice-vdagent \
         localsearch-3; do
    #   orca-autostart er skærmlæseren. Rammer nogen dens genvejstast,
    #   begynder maskinen at TALE — og ingen i stuen ved, hvordan man
    #   stopper den igen.
    #
    #   RØRT MED VILJE IKKE: im-launch (uden den kan tastaturet svigte),
    #   gnome-keyring (holder WiFi-nøglen), at-spi-dbus-bus. De åbner
    #   ingen vinduer, og de kan noget, vi har brug for.
    [[ -f "/etc/xdg/autostart/$d.desktop" ]] || continue
    cat > "$AUTOSTART/$d.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$d (slået fra af Livline)
Exec=/bin/true
Hidden=true
X-GNOME-Autostart-enabled=false
EOF
    chown "$KIOSK_USER":"$KIOSK_USER" "$AUTOSTART/$d.desktop"
    echo "   slået fra: $d"
done

# Firmware-opdateringer skal tages af dig over SSH, ikke meldes på en
# skærm i en fremmed stue. Snappen er kun en besked-boks.
if snap list firmware-updater &>/dev/null; then
    snap remove --purge firmware-updater 2>/dev/null \
        && echo "   firmware-updater-snappen fjernet" \
        || echo "   ADVARSEL: kunne ikke fjerne firmware-updater-snappen"
fi

# Bælte og seler: også selve beskederne slås fra, hvis skemaet findes
sudo -u "$KIOSK_USER" gsettings set com.ubuntu.update-notifier \
    no-show-notifications true 2>/dev/null || true

echo "-- Kontrollerer at de tidsstyrede opgaver er på plads..."
systemctl is-active --quiet cron \
    && echo "   cron kører ✔" \
    || echo "   ADVARSEL: cron kører ikke — nattevagt, netværkstjek, medie-"\
"oprydning og hardware-tjek vil IKKE køre. Undersøg med: systemctl status cron"
ls /etc/cron.d/livline-* 2>/dev/null | sed 's/^/   /'

# INGEN AF DE ROOT-KØRTE SCRIPTS MÅ LIGGE, HVOR KIOSK-BRUGEREN KAN SKRIVE.
# Kontrolleres til sidst, fordi det er den slags, der stille kan blive
# lavet om senere — af en genkørsel, en oprydning eller en god idé.
ROOTFEJL=0
for f in /usr/local/libexec/livline \
         /usr/local/libexec/livline/netcheck.sh \
         /usr/local/libexec/livline/hardware.py; do
    if [[ ! -e "$f" ]]; then
        echo "   ADVARSEL: $f mangler"
        ROOTFEJL=1
    elif [[ "$(stat -c '%U' "$f")" != "root" ]]; then
        echo "   ADVARSEL: $f ejes af $(stat -c '%U' "$f"), ikke root."
        echo "   Root kører den fra cron — så kan kiosk-brugeren blive root."
        ROOTFEJL=1
    elif sudo -u "$KIOSK_USER" test -w "$f" 2>/dev/null; then
        echo "   ADVARSEL: kiosk-brugeren kan skrive i $f"
        ROOTFEJL=1
    fi
done
[[ $ROOTFEJL -eq 0 ]] && echo "   root-opgaverne ligger uden for kiosk-brugerens rækkevidde ✔"

cat <<'SLUT'

== Færdig ==
Næste skridt:
 1. Genstart maskinen — den logger selv ind og starter Livline i fuldskærm.
    Du får en ✅-besked i din Telegram, når botten kører
 2. Bed familien søge botten frem i Telegram og trykke Start (= /start).
    De får svar med det samme, og du får en ⚠️-besked med navn, chat_id
    og en godkend-knap. Tryk på den, eller skriv /tilfoej <chat_id> <navn>.
    Navnet i Telegram er selvvalgt — godkend kun en, du selv har bedt om.

Husk i @BotFather: /setjoingroups -> Disable
Se byggevejledningen for strømstyring (8-22), TLP, Tailscale og kloning.
SLUT

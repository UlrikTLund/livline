#!/usr/bin/env bash
# Livline-PC installationsscript (Ubuntu 26.04 LTS)
INSTALL_VER="4.71"
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
    python3-pil.imagetk mpv ffmpeg \
    xvfb smartmontools fonts-noto-color-emoji cron openssl
#   ffmpeg          → beholdt: mpv bruger dens biblioteker til video
#                     (alsa-utils er væk sammen med talebesked-optagelsen)
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
FAILS=0
while true; do
    START=$(date +%s)
    if command -v systemd-cat >/dev/null 2>&1; then
        systemd-cat -t livline "$LIVLINE_PY" /opt/livline/livline_bot.py
    else
        "$LIVLINE_PY" /opt/livline/livline_bot.py 2>&1 | logger -t livline
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
        echo "   ADVARSEL: GDM logger automatisk ind som '$NUVAERENDE',"
        echo "   men appen er sat op til '$KIOSK_USER'. Skærmen vil stå tom."
        echo "   Ret AutomaticLogin i /etc/gdm3/custom.conf, eller kør igen."
    else
        echo "   autologin som $KIOSK_USER ✔"
    fi
else
    echo "   ADVARSEL: /etc/gdm3/custom.conf findes ikke — autologin er IKKE sat op."
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
cat > /opt/livline/netcheck.sh <<'EOF'
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
chmod 755 /opt/livline/netcheck.sh
echo "*/15 * * * * root /opt/livline/netcheck.sh" > /etc/cron.d/livline-net

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
cat > /opt/livline/hardware.py <<'EOF'
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
chmod 755 /opt/livline/hardware.py
echo "40 3 * * * root /usr/bin/python3 /opt/livline/hardware.py" \
    > /etc/cron.d/livline-hardware
/usr/bin/python3 /opt/livline/hardware.py 2>/dev/null || true

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
# KODEN TASTES. DEN SKRIVES ALDRIG SOM ARGUMENT.
# En kode på kommandolinjen havner i ~/.bash_history og i maskinens
# proces-liste, og den ville blive liggende i årevis på en maskine i en
# fremmed stue. Det var nær sket én gang; derfor findes denne fil.
#
# Nettet behøver IKKE være i nærheden. Familiens WiFi kan lægges ind,
# mens maskinen står på dit eget bord — og det er sådan, det skal gøres:
# der laves ikke teknik i stuen.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Kør med sudo."; exit 1; fi

if [[ $# -eq 0 ]]; then
    echo "Gemte net (maskinen vælger selv det, der er i nærheden):"
    nmcli -g NAME,TYPE connection show 2>/dev/null \
        | awk -F: '$2=="802-11-wireless"{print "   " $1}'
    echo
    echo "Net i nærheden lige nu:"
    nmcli -t -f SSID,SIGNAL device wifi list 2>/dev/null \
        | awk -F: 'NF && $1 != "" {print "   " $1 "  (" $2 "%)"}' | sort -u
    echo
    echo "Læg et nyt ind:   sudo livline-wifi \"Netværkets navn\""
    echo "Fjern et igen:    sudo livline-wifi --glem \"Netværkets navn\""
    exit 0
fi

if [[ "$1" == "--glem" ]]; then
    [[ $# -ge 2 ]] || { echo "Brug: sudo livline-wifi --glem \"navn\""; exit 1; }
    nmcli connection delete "$2" && echo "Fjernet: $2"
    exit 0
fi

SSID="$1"

# ER NETTET I NÆRHEDEN? Så lader vi nmcli spørge om koden selv. Den vej
# rører koden aldrig kommandolinjen — heller ikke et kort øjeblik.
if nmcli -t -f SSID device wifi list 2>/dev/null | grep -qxF "$SSID"; then
    echo "-- \"$SSID\" er i nærheden. Tast koden, når der bliver spurgt."
    nmcli --ask device wifi connect "$SSID"
    echo
    echo "Forbundet og gemt: $SSID"
    exit 0
fi

echo "-- \"$SSID\" er ikke i nærheden. Lægges ind til senere brug."
read -rsp "Kode til \"$SSID\" (tom = åbent net): " KODE; echo

if nmcli -g NAME connection show 2>/dev/null | grep -qxF "$SSID"; then
    echo "   findes i forvejen — opdaterer koden"
    if [[ -n "$KODE" ]]; then
        nmcli connection modify "$SSID" \
            wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$KODE"
    else
        nmcli connection modify "$SSID" wifi-sec.key-mgmt none
    fi
elif [[ -n "$KODE" ]]; then
    nmcli connection add type wifi con-name "$SSID" ssid "$SSID" \
        wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$KODE"
else
    nmcli connection add type wifi con-name "$SSID" ssid "$SSID"
fi
KODE=""

nmcli connection modify "$SSID" connection.autoconnect yes
echo
echo "Lagt ind: $SSID"
echo "Maskinen kobler sig selv på, næste gang nettet er i nærheden."
WIFIEOF
chmod 755 /usr/local/bin/livline-wifi
echo "   livline-wifi lagt på maskinen ✔"

echo "-- livline-vis: skift mellem de tre opsætninger..."
# Bruges ved levering: prøv alle tre med den ældre siddende foran, og vælg
# ud fra hvad hun FAKTISK gør. Pårørende svarer typisk for optimistisk om,
# hvad deres mor kan — det er svært at sige noget andet højt.
cat > /usr/local/sbin/livline-vis <<'EOF'
#!/usr/bin/env bash
# Skifter mellem de tre opsætninger og genstarter appen.
set -euo pipefail
case "${1:-}" in
  1) M=faellestraad; B=knapper  ;;
  2) M=faellestraad; B=tastatur ;;
  3) M=enkelte;      B=tastatur ;;
  *) echo "Brug: livline-vis 1|2|3"
     echo "  1  faste svar, én fælles samtale"
     echo "  2  frit skrivefelt, én fælles samtale"
     echo "  3  frit skrivefelt, én samtale pr. person"
     exit 1 ;;
esac
python3 - "$M" "$B" <<'PYEOF'
import json, pathlib, sys
p = pathlib.Path('/etc/livline/config.json')
d = json.loads(p.read_text())
d["mode"], d["betjening"] = sys.argv[1], sys.argv[2]
p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
PYEOF
pkill -f livline_bot.py || true
echo "Opsætning $1 — $M / $B. Skærmen skifter om et par sekunder."
EOF
chmod 755 /usr/local/sbin/livline-vis

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

echo "-- Medie-oprydning: familiens billeder/videoer slettes efter 30 dage..."
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

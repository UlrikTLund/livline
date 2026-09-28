#!/usr/bin/env python3
"""Prøver til livline_bot.py — køres FØR en ny version lægges i gisten.

    xvfb-run -a python3 livline-test.py

Hver prøve svarer til en fejl, der er set i drift. De er skrevet ned, fordi
en fejl, der er fundet én gang, ellers bliver fundet igen om et halvt år —
og fordi appens egen selvtest kun beviser, at vinduet kan bygges, ikke at
det opfører sig rigtigt.

Prøverne rører hverken Telegram eller den kørende maskine. De laver en
midlertidig config i /tmp og bygger brugerfladen i et usynligt skærmmiljø.
"""
import asyncio
import dataclasses
import importlib.util
import json
import os
import pathlib
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import types

STI = pathlib.Path(__file__).with_name("livline_bot.py")
ARBEJDE = pathlib.Path(tempfile.mkdtemp(prefix="livline-test-"))
CONFIG = ARBEJDE / "config.json"
WHITELIST = ARBEJDE / "whitelist.json"

CONFIG.write_text(json.dumps({
    "token": "123456:TESTTOKEN", "admin_chat_id": 1, "machine_name": "Prøve",
    "mode": "faellestraad", "betjening": "tastatur",
    "media_dir": str(ARBEJDE / "media"), "whitelist_path": str(WHITELIST),
    "update_url": "",
}, ensure_ascii=False))
WHITELIST.write_text("{}")
(ARBEJDE / "media").mkdir(exist_ok=True)

os.environ["LIVLINE_CONFIG"] = str(CONFIG)
spec = importlib.util.spec_from_file_location("lv", STI)
lv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lv)
import tkinter as tk                      # noqa: E402  (efter lv, som sætter miljøet)
import tkinter.font as tkfont             # noqa: E402

FEJL = []


def proev(navn):
    """Kører én prøve og fortsætter, selv om den fejler — så man ser ALLE
    problemer i én kørsel i stedet for det første."""
    def dekorator(fn):
        try:
            fn()
            print(f"  ✔ {navn}")
        except AssertionError as e:
            FEJL.append(navn)
            print(f"  ✘ {navn}: {e}")
        except Exception as e:
            FEJL.append(navn)
            print(f"  ✘ {navn}: {type(e).__name__}: {e}")
        return fn
    return dekorator


def luk(ui):
    """Lukker vinduet uden at efterlade ventende tidsstyrede kald.

    Uden det skriver Tk "invalid command name ...bund" midt i kørslen:
    appen har bedt om at blive kaldt igen om et par sekunder, og vinduet er
    væk, når kaldet kommer. Det kan ikke ske i drift, hvor vinduet lever,
    til maskinen slukker — men STØJ SKJULER RIGTIGE FEJL. Står der noget
    rødt næste gang, skal det betyde noget.

    TO FEJL ER RETTET HER, og begge var i prøveværktøjet — den værste
    slags, for de ligner fejl i programmet:

    1. Funktionen kaldte SIG SELV. Da alle "ui.root.destroy()" blev
       erstattet med "luk(ui)", ramte erstatningen også linjen inde i
       luk. 76 prøver faldt med RecursionError, og appen var uskyldig;
       dens egen selvtest kørte fint hele tiden.
    2. Der annulleres nu gennem Tcl direkte i stedet for tkinters
       after_cancel, som også rydder op i sit eget bogholderi undervejs."""
    try:
        for aid in ui.root.tk.splitlist(ui.root.tk.call("after", "info")):
            try:
                ui.root.tk.call("after", "cancel", aid)
            except Exception:
                pass
    except Exception:
        pass
    ui.root.destroy()


def byg(**afvigelser):
    c = lv.Config.load()
    if afvigelser:
        c = dataclasses.replace(c, **afvigelser)
    ui = lv.LivlineUI(c)
    ui.root.geometry(f"{ui.root.winfo_screenwidth()}x"
                     f"{ui.root.winfo_screenheight()}+0+0")
    ui.root.update()
    return ui


def bot(whitelist_indhold, **afvigelser):
    WHITELIST.write_text(json.dumps(whitelist_indhold))
    c = lv.Config.load()
    if afvigelser:
        c = dataclasses.replace(c, **afvigelser)
    return lv.BotWorker(c, lv.Whitelist(WHITELIST), queue.Queue())


def liste_tekster(ui):
    """Alle tekster i samtalelisten — også dem i indlejrede rammer."""
    fundet = []

    def gaa(w):
        for barn in w.winfo_children():
            try:
                fundet.append(str(barn.cget("text")))
            except tk.TclError:
                pass
            gaa(barn)
    gaa(ui.sidebar)
    return fundet


def status_for(ui, navn):
    """Statuslinjen under et navn i listen."""
    tekster = liste_tekster(ui)
    if navn in tekster:
        i = tekster.index(navn)
        if i + 1 < len(tekster):
            return tekster[i + 1]
    return None


def med_kvitteringsfanger():
    ui = med_tre_personer(blink=False)
    sendte = []
    ui.bot.send_text = lambda ids, tekst, svar=None: sendte.append((tuple(ids), tekst))
    return ui, sendte


print(f"\nPrøver mod livline_bot.py v{lv.VERSION}\n")

# ---------------------------------------------------------------- skrivefelt
print("Skrivefelt (betjening: tastatur)")


@proev("feltet starter på én linje og vokser med ombrudt tekst")
def _():
    ui = byg()
    assert int(ui.entry.cget("height")) == lv.FELT_MIN
    base = "Hej mor, tak for billedet af haven i gaar. "
    assert lv.FELT_MIN == 1, "feltet skal starte som én linje, ikke som en blok"
    hoejder = []
    for n in (1, 3, 6, 12):
        ui.entry.delete("1.0", "end")
        ui.entry.insert("1.0", base * n)
        ui.root.update()
        ui._juster_hoejde()
        hoejder.append(int(ui.entry.cget("height")))
    assert hoejder == sorted(hoejder), hoejder
    assert hoejder[-1] == lv.FELT_MAX, hoejder
    # ... og krymper igen, når beskeden er sendt
    ui._ryd_kladde()
    ui.root.update()
    ui._juster_hoejde()
    assert int(ui.entry.cget("height")) == lv.FELT_MIN
    luk(ui)


@proev("Enter sender og tømmer feltet; tom kladde sendes ikke")
def _():
    ui = byg()
    sendt = []
    ui._send_reply = sendt.append
    ui.entry.insert("1.0", "  Hej mor  \n")
    ui._send_typed()
    assert sendt == ["Hej mor"], sendt
    assert ui._kladde() == ""
    ui.entry.insert("1.0", "   \n  ")
    ui._send_typed()
    assert sendt == ["Hej mor"], "tom kladde blev sendt"
    luk(ui)


@proev("uafsendt tekst sendes selv efter 5 min. — og aldrig før")
def _():
    ui = byg()
    sendt = []
    ui._send_reply = sendt.append
    ui.entry.insert("1.0", "glemt besked")
    ui._last_key = time.monotonic()
    ui._autosend_check()
    assert sendt == [], "sendte for tidligt"
    ui._last_key = time.monotonic() - (lv.IDLE_RESET_SEC + 1)
    ui._autosend_check()
    assert sendt == ["glemt besked"], sendt
    luk(ui)


@proev("autosend: 0 slår funktionen helt fra")
def _():
    ui = byg(autosend=0)
    ui._send_reply = lambda t: (_ for _ in ()).throw(
        AssertionError("sendte trods autosend=0"))
    ui.entry.insert("1.0", "må ikke sendes")
    ui._last_key = time.monotonic() - 9999
    ui._autosend_check()
    luk(ui)


@proev("skrivefeltet ser ud som brugerens egen boble")
def _():
    ui = byg()
    boble = ui._boble("Prøvesvar", "12:00", None, egen=True)
    ui.root.update()
    assert str(ui.entry.cget("bg")) == str(boble.cget("bg")), "andet fyld end boblen"
    assert str(ui.entry.cget("highlightbackground")) == ui._kant_ud, "anden kant"
    assert int(ui.entry.cget("padx")) == int(boble.cget("padx")), "anden luft"
    luk(ui)


# ------------------------------------------------------------------- layout
print("\nLayout")


@proev("intet ryger uden for skærmen ved skrift 26/28/34/44")
def _():
    # Der er ingen Send-knap mere (4.42), så det er FELTET selv, der
    # måles: det må ikke blive bredere end skærmen ved stor skrift, og
    # samtalen må ikke blive klemt.
    for skrift in (26, 28, 34, 44):
        ui = byg(font_size=skrift, show_buttons=True)
        ui.root.geometry(f"{ui.root.winfo_screenwidth()}x"
                         f"{ui.root.winfo_screenheight()}+0+0")
        ui.root.update(); ui.root.update_idletasks()
        sb, sh = ui.root.winfo_screenwidth(), ui.root.winfo_screenheight()
        assert not [w for w in ui.entry.master.winfo_children()
                    if isinstance(w, tk.Button)], \
            "der er en knap ved skrivefeltet — den skulle være fjernet"
        assert ui.entry.winfo_rootx() + ui.entry.winfo_width() <= sb + 2, \
            f"skrivefeltet rager ud til siden ved skrift {skrift}"
        assert ui.entry.winfo_rooty() + ui.entry.winfo_height() <= sh + 2, \
            f"skrivefeltet rager ud i bunden ved skrift {skrift}"
        assert ui.text.winfo_height() > sh * 0.4, \
            f"beskedfeltet blev klemt ved skrift {skrift}"
        luk(ui)


@proev("et stort billede bliver inde i tekstfeltet")
def _():
    # SET VED GENNEMGANG: billedernes maksbredde blev regnet ud af SKÆRMEN
    # (1840 px på 1920) og lagt i et tekstfelt på 1403 px, fordi
    # samtalelisten tager af bredden. Tredje gang samme fejl — boblerne og
    # skrivefeltet var de to første.
    #
    # Der måles på det FÆRDIGE billede, ikke på formlen: en prøve, der
    # regner det samme ud som koden, prøver kun sig selv.
    from PIL import Image
    foto = ARBEJDE / "media" / "stort.jpg"
    Image.new("RGB", (4000, 3000), (120, 80, 60)).save(foto)
    WHITELIST.write_text(json.dumps({"11": "Mor", "22": "Jens", "33": "Anne"}))
    ui = byg(mode="enkelte", blink=False, bubbles=False)
    ui.whitelist = lv.Whitelist(WHITELIST)
    ui.bot.whitelist = ui.whitelist
    ui.root.geometry(f"{ui.root.winfo_screenwidth()}x"
                     f"{ui.root.winfo_screenheight()}+0+0")
    try:
        ui.root.update()
        ui._juster_bredder()
        ui._modtag_til_skaerm(
            lv.Incoming("Mor", 11, "photo", text="", file_path=foto))
        ui.root.update()
        ui.root.update_idletasks()
        billeder = [b for b in ui._img_refs if hasattr(b, "width")]
        assert billeder, "billedet blev ikke vist"
        bredest = max(b.width() for b in billeder)
        plads = ui.text.winfo_width() - 2 * ui.config.margin
        assert bredest <= plads, (
            f"billedet blev {bredest} px bredt i et felt med {plads} px plads "
            f"— {bredest - plads} px ud over kanten")
    finally:
        luk(ui)
        WHITELIST.write_text("{}")
        foto.unlink(missing_ok=True)


@proev("en lang besked bliver inde i sin spalte — også egne svar")
def _():
    # SET I DRIFT: en afsendt besked løb ud over VENSTRE kant med halve
    # bogstaver. Boblens maksimale bredde blev regnet ud af SKÆRMEN, mens
    # spalten, den skulle stå i, blev regnet ud af tekstfeltet — som er
    # smallere, fordi samtalelisten tager af venstresiden. Egne svar er
    # højrestillede, så overskuddet gik ud til venstre.
    #
    # Samme rod som skrivefeltet havde: to grundlag for det samme mål.
    lang = ("Det her er et ret langt svar, som skal fylde hele spalten "
            "og gerne mere end den, hvis noget er galt med bredden")
    for mode in ("enkelte", "faellestraad"):
        WHITELIST.write_text(json.dumps({"11": "Mor", "22": "Jens", "33": "Anne"}))
        ui = byg(mode=mode, blink=False)
        ui.whitelist = lv.Whitelist(WHITELIST)
        ui.bot.whitelist = ui.whitelist
        ui.bot.send_text = lambda *a, **k: None
        ui.root.geometry(f"{ui.root.winfo_screenwidth()}x"
                         f"{ui.root.winfo_screenheight()}+0+0")
        try:
            ui.root.update()
            ui._juster_bredder()
            ui._modtag_til_skaerm(lv.Incoming("Mor", 11, "text", text=lang))
            ui._send_reply(lang)
            ui.root.update()
            ui.root.update_idletasks()
            t_v = ui.text.winfo_rootx()
            t_h = t_v + ui.text.winfo_width()
            bobler = list(ui.text.winfo_children())
            assert bobler, "ingen bobler at måle"
            for b in bobler:
                v = b.winfo_rootx()
                h = v + b.winfo_width()
                assert v >= t_v - 2, (
                    f"{mode}: boble begynder ved {v}, tekstfeltet ved {t_v} "
                    f"— {t_v - v} px ud over venstre kant")
                assert h <= t_h + 2, (
                    f"{mode}: boble slutter ved {h}, tekstfeltet ved {t_h}")
        finally:
            luk(ui)
            WHITELIST.write_text("{}")


@proev("boblen ombryder samme sted som skrivefeltet")
def _():
    # SET I DRIFT: en sætning, der lige passede på én linje i feltet, tabte
    # et par bogstaver ned på næste linje, når den blev til en boble.
    # Boblen ombrød 8 % smallere end feltet — endnu en uenighed mellem to
    # tal, der skulle være ét.
    WHITELIST.write_text(json.dumps({"11": "Mor", "22": "Jens"}))
    ui = byg(mode="enkelte", blink=False)
    ui.whitelist = lv.Whitelist(WHITELIST)
    ui.bot.whitelist = ui.whitelist
    ui.root.geometry(f"{ui.root.winfo_screenwidth()}x"
                     f"{ui.root.winfo_screenheight()}+0+0")
    try:
        ui.root.update()
        ui._juster_bredder()
        ui.root.update_idletasks()
        felt = (ui.entry.winfo_width()
                - 2 * int(ui.entry.cget("padx"))
                - 2 * int(ui.entry.cget("highlightthickness")))
        # Der SPØRGES boblen om dens ombrydning — regnes den ud med samme
        # formel som koden, prøver man kun sin egen formel. (Den første
        # udgave af prøven gjorde netop det og lod fejlen slippe igennem.)
        ramme = ui._boble("en prøvebesked", "kl. 12.00 i dag", None, egen=True)
        ui.root.update_idletasks()
        wraps = []
        for w in ramme.winfo_children():
            try:                      # cget kan give et Tcl-objekt
                v = int(str(w.cget("wraplength")))
            except (tk.TclError, ValueError):
                continue
            if v > 0:
                wraps.append(v)
        assert wraps, "boblen har ingen ombrydningsbredde at måle"
        boble = max(wraps)
        assert abs(felt - boble) <= 8, (
            f"feltet ombryder ved {felt} px, boblen ved {boble} px "
            f"— {abs(felt - boble)} px fra hinanden, og så flytter ord sig")
    finally:
        luk(ui)
        WHITELIST.write_text("{}")


@proev("skrivefeltet står i samme spalte som beskederne")
def _():
    # SET I DRIFT: feltet begyndte 217 px længere til venstre end nogen
    # boble, fordi det blev centreret i HELE vinduet, mens beskederne
    # centreres inde i tekstfeltet — som starter til højre for
    # samtalelisten. Når man skrev, løb teksten altså ud over den spalte,
    # samtalen ellers holder sig i.
    #
    # Der måles med OG uden sideliste, for det var netop listen, der
    # gjorde de to regler uenige.
    for mode, navne in (("enkelte", {"11": "Mor", "22": "Jens", "33": "Anne"}),
                        ("faellestraad", {"11": "Mor"})):
        WHITELIST.write_text(json.dumps(navne))
        ui = byg(mode=mode, blink=False)
        ui.whitelist = lv.Whitelist(WHITELIST)
        ui.bot.whitelist = ui.whitelist
        ui.root.geometry(f"{ui.root.winfo_screenwidth()}x"
                         f"{ui.root.winfo_screenheight()}+0+0")
        try:
            # besked() er defineret længere nede i filen — her sendes den
            # direkte, så prøven kan stå sammen med de øvrige layoutprøver.
            ui._modtag_til_skaerm(
                lv.Incoming("Mor", 11, "text", text="en helt almindelig besked"))
            ui.root.update()
            # _juster_bredder retter BÅDE spalten og feltet. Kaldes kun
            # feltet, står tekstmærkerne stadig med den gamle indrykning,
            # og de to bliver uenige — det afslørede prøven her selv.
            ui._juster_bredder()
            ui.root.update_idletasks()
            bobler = [w for w in ui.text.winfo_children()]
            assert bobler, "ingen boble at måle mod"
            boble_v = bobler[0].winfo_rootx()
            felt_v = ui.entry.winfo_rootx()
            assert abs(felt_v - boble_v) <= 8, (
                f"{mode}: skrivefeltet begynder ved {felt_v}, "
                f"boblen ved {boble_v} — {abs(felt_v - boble_v)} px forskudt")
            # ... og feltet må ikke rage ud over tekstfeltet
            assert felt_v >= ui.text.winfo_rootx() - 2, \
                f"{mode}: feltet begynder til venstre for beskedfeltet"
            assert (ui.entry.winfo_rootx() + ui.entry.winfo_width()
                    <= ui.text.winfo_rootx() + ui.text.winfo_width() + 2), \
                f"{mode}: feltet rager ud til højre for beskedfeltet"
        finally:
            luk(ui)
            WHITELIST.write_text("{}")


@proev("skrivefeltet bruger en fornuftig del af skærmbredden")
def _():
    # Målt i drift: feltet var 27 % af en 1920 px skærm, fordi margenen
    # (1/6 i hver side) blev lagt oveni samtalelisten OG Send-knappen.
    # 1396 px stod tomme. Prøven holder øje med, at det ikke sker igen —
    # og med begge yderpunkter, for et felt tværs over hele skærmen blev
    # også forkastet, fordi det virker uroligt.
    # VIGTIGT: der måles i den VÆRSTE opstilling — enkelte-tilstand med
    # flere personer, så samtalelisten er fremme. Uden den er feltet
    # bredere af sig selv, og prøven ville lade fejlen slippe igennem.
    # (Det gjorde den første udgave af netop denne prøve.)
    WHITELIST.write_text(json.dumps({"11": "Mor", "22": "Jens", "33": "Anne"}))
    try:
        for knapper in (True, False):
            ui = byg(mode="enkelte", show_buttons=knapper)
            ui.whitelist = lv.Whitelist(WHITELIST)
            ui.bot.whitelist = ui.whitelist
            ui.root.geometry(f"{ui.root.winfo_screenwidth()}x"
                             f"{ui.root.winfo_screenheight()}+0+0")
            ui._refresh_topbar()
            ui.root.update()
            ui.root.update_idletasks()
            sb = ui.root.winfo_screenwidth()
            andel = ui.entry.winfo_width() / sb
            luk(ui)
            # Der er ingen Send-knap længere, så "vis_knapper" må ikke
            # kunne gøre feltet smallere i skrivefelt-tilstand.
            assert 0.50 <= andel <= 0.85, (
                f"skrivefeltet fylder {andel:.0%} af bredden "
                f"(vis_knapper={knapper}) — ventede mellem 50 og 85 %")
    finally:
        WHITELIST.write_text("{}")


@proev("teksten fylder samme andel af skærmhøjden, uanset skærm og skalering")
def _():
    # Set i drift: en 14" skærm på 3072x1728 meldte sig som 813x457 mm, og
    # oveni lå skrivebordets 200 %-forstørrelse. Samme tal gav 33 px på én
    # maskine og 88 px på en anden. Derfor måles og rettes der nu til.
    ui = byg()
    hoejde = ui.root.winfo_screenheight()
    # VIGTIGT: Tk deler skalering mellem alle vinduer i samme program, så
    # den skal sættes tilbage bagefter. Ellers arver de næste prøver den —
    # og en af dem meldte en fejl, der slet ikke fandtes (tegnet 2058 px
    # fra teksten, fordi skriften var beregnet ved skalering 10).
    oprindelig = float(ui.root.tk.call("tk", "scaling"))
    for paastand in (0.8, 1.3333, 2.0, 2.6667):
        ui.root.tk.call("tk", "scaling", paastand)
        rettet = ui._tilpas_skrift(28)
        px = tkfont.Font(family="DejaVu Sans", size=rettet).metrics("linespace")
        maal = hoejde * lv.SKRIFT_ANDEL * 28
        afvigelse = abs(px - maal) / maal
        assert afvigelse < 0.12, (
            f"ved skalering {paastand}: {px} px mod mål {round(maal)} px "
            f"({round(afvigelse * 100)} % ved siden af)")
    ui.root.tk.call("tk", "scaling", oprindelig)
    luk(ui)


@proev("en umulig skærm giver stadig en brugbar skrift")
def _():
    # Justeringen må aldrig løbe løbsk eller vælte appen, uanset hvad
    # skærmen påstår. Værste tilfælde skal stadig give læsbar tekst.
    ui = byg()
    loft = ui.root.winfo_screenheight() // 12
    oprindelig = float(ui.root.tk.call("tk", "scaling"))
    for paastand in (0.1, 10.0):
        ui.root.tk.call("tk", "scaling", paastand)
        rettet = ui._tilpas_skrift(28)
        assert 8 <= rettet <= loft, f"skrift {rettet} ved skalering {paastand}"
    ui.root.tk.call("tk", "scaling", oprindelig)   # se noten ovenfor
    luk(ui)


@proev("man kan se, hvem man skriver til — både øverst og ved feltet")
def _():
    # Set i drift: med tre navne på skærmen lod F-tasterne ikke til at gøre
    # noget. De virkede, men markeringen var en lille pil inde i rækken.
    WHITELIST.write_text(json.dumps({"11": "Mor", "22": "Jens", "33": "Anne"}))
    ui = byg(mode="enkelte")
    ui.whitelist = lv.Whitelist(WHITELIST)
    ui.bot.whitelist = ui.whitelist
    ui._select_fkey(0)
    ui.root.update()
    top = ui._top_tekst.cget("text")
    hjaelp = ui._hjaelp.cget("text")
    assert "MOR" in top, f"modtageren fremhæves ikke øverst: {top!r}"
    # Den viste samtale står KUN i hovedet (v4.29) — listen er dem, der venter
    samlet = " ".join(liste_tekster(ui))
    assert "Jens" in samlet and "Anne" in samlet, \
        f"de øvrige kan ikke vælges: {samlet!r}"
    assert "Mor" not in samlet, \
        f"den viste samtale står både i hovedet og i listen: {samlet!r}"
    assert "Skriver til Mor" in hjaelp, f"feltet siger ikke hvem: {hjaelp!r}"

    ui._select_fkey(1)                    # F4 -> Jens
    ui.root.update()
    assert "JENS" in ui._top_tekst.cget("text"), "skiftet ses ikke øverst"
    assert "Skriver til Jens" in ui._hjaelp.cget("text"), "skiftet ses ikke ved feltet"

    # en tast uden person må ikke ændre noget
    foer = ui._top_tekst.cget("text")
    ui._select_fkey(4)
    ui.root.update()
    assert ui._top_tekst.cget("text") == foer, "tom tast flyttede modtageren"
    luk(ui)
    WHITELIST.write_text("{}")


# ------------------------------------------------------- én samtale ad gangen
print("\nSamtaler (mode: enkelte)")


def med_tre_personer(**ekstra):
    WHITELIST.write_text(json.dumps({"11": "Mor", "22": "Jens", "33": "Anne"}))
    ui = byg(mode="enkelte", **ekstra)
    ui.whitelist = lv.Whitelist(WHITELIST)
    ui.bot.whitelist = ui.whitelist
    return ui


def besked(ui, chat_id, navn, tekst):
    ui._modtag_til_skaerm(lv.Incoming(navn, chat_id, "text", text=tekst))
    ui.root.update()


def paa_skaermen(ui):
    """Alt, hvad der faktisk står på skærmen — også inde i boblerne, som er
    selvstændige widgets indlejret i tekstfeltet."""
    dele = [ui.text.get("1.0", "end")]
    for ramme in ui.text.winfo_children():
        for barn in ramme.winfo_children():
            try:
                dele.append(str(barn.cget("text")))
            except tk.TclError:
                pass
    return "\n".join(dele)


@proev("skærmen viser kun den valgte samtale — ikke alles beskeder blandet")
def _():
    ui = med_tre_personer()
    besked(ui, 11, "Mor", "besked fra mor")
    besked(ui, 22, "Jens", "besked fra jens")
    # står nu i Jens' samtale (nyeste). Mors besked må ikke stå der
    ui._select_fkey(0)                       # F2 -> Mor
    ui.root.update()
    assert "besked fra mor" in paa_skaermen(ui), "mors besked mangler"
    assert "besked fra jens" not in paa_skaermen(ui), \
        "Jens' besked står i Mors samtale"
    ui._select_fkey(1)                       # F4 -> Jens
    ui.root.update()
    assert "besked fra jens" in paa_skaermen(ui)
    assert "besked fra mor" not in paa_skaermen(ui)
    luk(ui)


@proev("skærmen skifter ALDRIG samtale af sig selv")
def _():
    ui = med_tre_personer()
    besked(ui, 11, "Mor", "første besked")
    valgt_start = ui.selected
    besked(ui, 22, "Jens", "ny besked")
    besked(ui, 33, "Anne", "og en mere")
    ui.root.update()
    assert ui.selected == valgt_start, "skærmen skiftede uden et tastetryk"
    assert {22, 33} <= ui._venter, "de nye samtaler blev ikke markeret"
    # heller ikke efter at der er kvitteret
    ui._select_fkey(0)
    besked(ui, 22, "Jens", "endnu en")
    ui.root.update()
    assert ui.selected == 11, "skærmen skiftede efter kvittering"
    # kun F-tasten flytter den
    ui._select_fkey(1)
    ui.root.update()
    assert ui.selected == 22 and "ny besked" in paa_skaermen(ui)
    luk(ui)


@proev("Enter med tomt felt kvitterer — Enter med tekst sender")
def _():
    ui, sendte = med_kvitteringsfanger()
    besked(ui, 11, "Mor", "har du set det?")
    ui.root.update()
    assert sendte == [], "kvitterede uden tastetryk"

    ui._send_typed()                     # tomt felt + Enter
    ui.root.update()
    assert len(sendte) == 1 and sendte[0][0] == (11,), \
        f"tomt Enter kvitterede ikke: {sendte}"

    # ... og med tekst sendes teksten i stedet (den rigtige vej, så
    # kvitteringen inde i _send_reply også kommer med)
    sendte.clear()
    besked(ui, 11, "Mor", "og lige en til")
    assert 11 in ui._ukvitteret
    ui.entry.insert("1.0", "ja jeg har set det")
    ui._send_typed()
    ui.root.update()
    assert any("ja jeg har set det" in x[1] for x in sendte), \
        f"teksten blev ikke sendt: {sendte}"
    assert not any(lv.KVIT_MAERKE in x[1] for x in sendte), \
        "sendte en kvittering oveni svaret"
    assert 11 not in ui._ukvitteret, "svaret kvitterede ikke"
    luk(ui)


@proev("en tast, der holdes nede, sender ÉN besked — ikke tredive")
def _():
    # SET I DRIFT: holdes en svartast nede, gentager tastaturet den mange
    # gange i sekundet. Familien fik en byge af ens beskeder, og for dem
    # ligner det panik. Hun så kun, at boblerne blev ved med at komme.
    ui, sendte = med_kvitteringsfanger()
    besked(ui, 11, "Mor", "hej")
    sendte.clear()

    for _i in range(30):                 # tastaturets gentagelse
        ui._send_reply("Tak")
    ui.root.update()
    svar = [x for x in sendte if "Tak" in x[1]]
    assert len(svar) == 1, f"{len(svar)} beskeder sendt i stedet for én"

    # Et ANDET svar er en ny beslutning og må ikke bremses
    ui._send_reply("Ring til mig")
    ui.root.update()
    assert any("Ring til mig" in x[1] for x in sendte), \
        "et andet svar blev også bremset — så kan hun ikke skifte mening"

    # … men SKIFTEVIS to taster må heller ikke slippe igennem i en strøm.
    # Q, X, Q, X er aldrig "samme svar", så den første spærring fangede
    # ingenting. Familien fik "Tak, Nej tak, Tak, Nej tak" i lang række,
    # og for dem ligner det panik — ikke en skælvende finger.
    ui._sidste_svar = 0.0
    ui._sidste_svar_tekst = ""
    ui._svar_tider = []
    sendte.clear()
    for _i in range(15):
        ui._send_reply("Tak")
        ui._send_reply("Nej tak")
    ui.root.update()
    assert len(sendte) <= lv.SVAR_MAKS_I_VINDUE, \
        f"{len(sendte)} svar sluppet igennem ved skiftevise taster"

    # … og efter pausen må det samme svar sendes igen
    ui._sidste_svar -= lv.SVAR_PAUSE_SEK + 1
    ui._send_reply("Tak")
    ui.root.update()
    assert len([x for x in sendte if "Tak" in x[1]]) == 2, \
        "svaret kunne ikke sendes igen efter pausen"
    luk(ui)


@proev("én defekt besked må ikke gøre maskinen døv for altid")
def _():
    # DEN ALVORLIGSTE FEJL I PROGRAMMET. _poll_inbox bestilte sit næste
    # gennemløb til SIDST i funktionen. Kastede én besked en fejl undervejs
    # — fx en halvt skrevet billedfil — nåede den linje aldrig, og løkken
    # stoppede for altid. Vinduet stod og så levende ud, tasterne virkede,
    # rulningen virkede. Ingen besked kom nogensinde igennem igen, og
    # processen døde ikke, så genstartsvagten opdagede intet.
    #
    # Prøven kører i FÆLLESTRÅD, fordi det er den tilstand, maskinerne
    # leveres i. I "enkelte" viskes advarselslinjen af skærmen, næste gang
    # en samtale tegnes om — derfor er meldingen til administrator det,
    # der altid holder. Han er også den eneste, der kan gøre noget.
    ui = byg(mode="faellestraad", blink=False)
    sendte = []
    ui.bot.send_text = lambda ids, tekst, svar=None: sendte.append((tuple(ids), tekst))
    try:
        rigtig = ui._modtag_til_skaerm
        kaldt = []

        def sprænger(m):
            kaldt.append(m)
            if len(kaldt) == 1:
                raise RuntimeError("defekt billedfil")
            return rigtig(m)

        ui._modtag_til_skaerm = sprænger
        ui.inbox.put(lv.Incoming("Mor", 11, "photo", text="",
                                 file_path=pathlib.Path("/tmp/ikke-et-billede")))
        ui.inbox.put(lv.Incoming("Mor", 11, "text", text="kommer du i morgen?"))
        ui._poll_inbox()
        ui.root.update()

        assert len(kaldt) == 2, \
            "den næste besked blev aldrig forsøgt — én fejl tog resten med sig"
        assert "kommer du i morgen" in paa_skaermen(ui), \
            "beskeden efter den defekte nåede aldrig skærmen"
        assert "kunne ikke vises" in paa_skaermen(ui).lower(), \
            "den defekte besked forsvandt uden et ord på skærmen"
        assert any("kunne ikke" in t.lower() and "VISE" in t for _i, t in sendte), \
            f"administrator fik intet at vide om visningsfejlen: {sendte}"
        # … men kun ÉN gang, selv om alle beskeder fejler
        antal_foer = len(sendte)
        kaldt.clear()
        ui._modtag_til_skaerm = lambda m: (_ for _ in ()).throw(
            RuntimeError("stadig defekt"))
        for _i in range(5):
            ui.inbox.put(lv.Incoming("Mor", 11, "text", text="igen"))
        ui._poll_inbox()
        ui.root.update()
        assert len(sendte) == antal_foer, \
            "administrator fik en melding pr. besked — det er en byge, ikke en advarsel"
        # Og løkken skal have bestilt sit næste gennemløb
        assert ui.root.tk.call("after", "info"), \
            "der er ikke bestilt et nyt gennemløb — maskinen er døv"
    finally:
        luk(ui)


@proev("en ulæst besked er stadig ulæst efter genstarten kl. 3")
def _():
    # HVER NAT. Familien skriver kl. 23.30, han sover, maskinen genstarter
    # kl. 3. _load_history genskabte beskederne på skærmen, men ikke
    # _ukvitteret — så om morgenen stod der "Læst 23.30" med grønt flueben,
    # familien havde aldrig fået kvitteringen, og trykkede han Enter, skete
    # der ingenting.
    hist = ARBEJDE / "historik.json"
    WHITELIST.write_text(json.dumps({"111": "Ulrik"}))
    ui = byg(mode="faellestraad", blink=False)
    ui.whitelist = lv.Whitelist(WHITELIST)
    try:
        besked(ui, 111, "Ulrik", "sover du?")
        assert 111 in ui._ukvitteret, "ventelisten virker slet ikke"
        hist.write_text(json.dumps(ui._rows, ensure_ascii=False),
                        encoding="utf-8")
    finally:
        luk(ui)

    # … og nu som efter genstarten kl. 3: ny brugerflade, samme historik
    ui = byg(mode="faellestraad", blink=False)
    ui.whitelist = lv.Whitelist(WHITELIST)
    try:
        ui._load_history()
        ui.root.update()
        assert 111 in ui._ukvitteret, \
            "beskeden blev regnet for læst efter genstart — " \
            "familien fik aldrig en kvittering, og Enter gør ingenting"
    finally:
        hist.unlink(missing_ok=True)
        WHITELIST.write_text("{}")
        luk(ui)


@proev("et eget svar i historikken rydder ventelisten igen")
def _():
    # Modstykket: har han svaret, må beskeden ikke stå som ulæst bagefter,
    # for så ville maskinen bede om en kvittering, der allerede er givet.
    hist = ARBEJDE / "historik.json"
    WHITELIST.write_text(json.dumps({"111": "Ulrik"}))
    ui = byg(mode="faellestraad", blink=False)
    ui.whitelist = lv.Whitelist(WHITELIST)
    try:
        besked(ui, 111, "Ulrik", "sover du?")
        raekker = list(ui._rows)
        raekker.append({"navn": "Du", "chat_id": 111, "type": "text",
                        "tekst": "Tak", "fil": None,
                        "tid": raekker[-1]["tid"], "egen": True})
        hist.write_text(json.dumps(raekker, ensure_ascii=False),
                        encoding="utf-8")
    finally:
        luk(ui)

    ui = byg(mode="faellestraad", blink=False)
    ui.whitelist = lv.Whitelist(WHITELIST)
    try:
        ui._load_history()
        assert not ui._ukvitteret, \
            f"han havde svaret, men står stadig som skyldig: {ui._ukvitteret}"
    finally:
        hist.unlink(missing_ok=True)
        WHITELIST.write_text("{}")
        luk(ui)


@proev("en ulæselig historik siges højt i stedet for at ligne en tom skærm")
def _():
    # En tom skærm læses som "ingen har skrevet". Det er en helt anden
    # besked end "jeg kan ikke komme til det, der er skrevet".
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    blok = kilde.split("def _load_history")[1].split("def ")[0]
    assert "log.warning" in blok, "en ulæselig historik forsvinder i tavshed"
    assert "_historik_fejl" in blok, "skærmen får intet at vide om fejlen"
    assert "Tidligere beskeder kunne ikke læses" in kilde, \
        "brugeren ser ikke, at der mangler noget"


@proev("hjælpelinjen siger, hvad Enter gør lige nu")
def _():
    ui = med_tre_personer(blink=False)
    besked(ui, 11, "Mor", "hej")
    ui.root.update()
    assert "har set beskeden" in ui._hjaelp.cget("text"), \
        f"siger ikke, at Enter kvitterer: {ui._hjaelp.cget('text')!r}"
    ui._send_typed()                     # kvitterer
    ui.root.update()
    assert "Skriver til Mor" in ui._hjaelp.cget("text"), \
        f"skiftede ikke tilbage: {ui._hjaelp.cget('text')!r}"
    assert len(ui._hjaelp.cget("text")) < 45, "linjen er for lang til at blive læst"
    luk(ui)


@proev("at rulle kvitterer IKKE — piletasterne kører også af sig selv")
def _():
    # Efter 5 minutters stilstand ruller maskinen selv ned til nyeste besked.
    # Talte rulning som kvittering, ville maskinen kvittere på brugerens
    # vegne, mens hun sad i den anden stue.
    ui, sendte = med_kvitteringsfanger()
    besked(ui, 11, "Mor", "har du set det?")
    ui._scroll(1)
    ui._scroll(-1)
    ui.root.update()
    assert sendte == [], f"rulning sendte kvittering: {sendte}"
    assert 11 in ui._ukvitteret, "beskeden blev regnet for læst"
    luk(ui)


@proev("ét tryk på pilen ruller en fjerdedel af SKÆRMEN, ikke af samtalen")
def _():
    # Den gamle udgave rullede 8 % af ALT indhold. Med fem beskeder var det
    # ingenting; med hundrede var ét tryk flere skærmfulde, og brugeren mistede
    # det, hun lige sad og læste. Skridtet skal måles i skærme — det er den
    # eneste enhed, der betyder det samme hver gang.
    ui = med_tre_personer(blink=False)
    for i in range(60):
        besked(ui, 11, "Mor", f"besked nummer {i} med lidt tekst i")
    ui.root.update()

    # Stil synet midt i samtalen FØRST. Hvor rulningen tilfældigvis står
    # efter 60 beskeder afhænger af, om _rul_til_bund har nået at køre —
    # og prøven her handler om _scroll's regnestykke, ikke om den. Første
    # udgave målte fra toppen, hvor pil op med rette ikke flytter noget,
    # og meldte så fejl på en app, der gjorde det rigtige.
    ui.text.yview_moveto(0.5)
    ui.root.update()

    top, bund = ui.text.yview()
    synlig = bund - top
    assert synlig < 0.5, \
        f"prøven er for kort til at måle noget (ser {synlig:.0%} af alt)"

    foer = ui.text.yview()[0]
    assert foer > 0.0, "synet står i toppen — så kan pil op ikke måles"
    ui._scroll(-1)                        # pil op
    ui.root.update()
    skridt = foer - ui.text.yview()[0]

    assert skridt > 0, "pil op flyttede ingenting"
    assert skridt <= synlig * lv.RUL_ANDEL + 0.002, \
        (f"ét tryk flyttede {skridt:.3f} — mere end {lv.RUL_ANDEL:.0%} "
         f"af de {synlig:.3f}, der er på skærmen")
    assert skridt < synlig, \
        "ét tryk slugte hele skærmen — der skal blive noget læst tilbage"
    luk(ui)


@proev("rulning virker også i en kort samtale og løber ikke ud over kanten")
def _():
    ui = med_tre_personer(blink=False)
    besked(ui, 11, "Mor", "hej")
    ui.root.update()
    for _i in range(20):
        ui._scroll(-1)
    ui.root.update()
    assert ui.text.yview()[0] >= 0.0, "rullede op over toppen"
    for _i in range(20):
        ui._scroll(1)
    ui.root.update()
    assert ui.text.yview()[0] <= 1.0, "rullede ned under bunden"
    luk(ui)


@proev("rul-til-bunden efter 5 min. skifter ikke samtale og kvitterer ikke")
def _():
    ui, sendte = med_kvitteringsfanger()
    besked(ui, 11, "Mor", "hej")          # står ubesvaret på skærmen
    besked(ui, 22, "Jens", "venter")      # må derfor ikke hente skærmen
    assert ui.selected == 11 and 22 in ui._venter
    sendte.clear()
    ui._last_key = time.monotonic() - (lv.IDLE_RESET_SEC + 1)
    ui._idle_check()
    ui.root.update()
    assert ui.selected == 11, "den automatiske rulning skiftede samtale"
    assert sendte == [], f"den automatiske rulning kvitterede: {sendte}"
    assert 22 in ui._venter, "den ventende samtale blev ryddet"
    luk(ui)


@proev("en ny besked afbryder ikke en halv sætning")
def _():
    ui = med_tre_personer()
    besked(ui, 11, "Mor", "hej fra mor")
    ui.entry.insert("1.0", "jeg er midt i en sætning")
    besked(ui, 22, "Jens", "afbryder ikke")
    assert ui.selected == 11, "skærmen skiftede midt i en sætning"
    assert "afbryder ikke" not in paa_skaermen(ui)
    assert ui._kladde() == "jeg er midt i en sætning", "kladden gik tabt"
    tekster = liste_tekster(ui)
    assert any(x.startswith("Ny besked") for x in tekster), \
        f"den ventende samtale er ikke markeret i listen: {tekster!r}"
    # sætningen sendes — skærmen bliver stadig stående, indtil hun selv skifter
    ui._send_reply = lambda t: None
    ui._send_typed()
    ui.root.update()
    assert ui.selected == 11, "skærmen skiftede af sig selv efter afsendelse"
    assert 22 in ui._venter, "markeringen forsvandt"
    luk(ui)


@proev("egne svar bliver i den samtale, de blev sendt i")
def _():
    ui = med_tre_personer()
    besked(ui, 11, "Mor", "hej fra mor")
    ui._select_fkey(0)
    ui._send_reply("mit svar til mor")
    ui.root.update()
    assert "mit svar til mor" in paa_skaermen(ui)
    ui._select_fkey(1)                       # over til Jens
    ui.root.update()
    assert "mit svar til mor" not in paa_skaermen(ui), \
        "svaret til Mor står i Jens' samtale"
    luk(ui)
    WHITELIST.write_text("{}")


@proev("listen viser dem, der IKKE er fremme — den viste står i hovedet")
def _():
    ui = med_tre_personer()
    besked(ui, 11, "Mor", "hej mor")
    ui._select_fkey(0)                       # står i Mors samtale
    ui.entry.insert("1.0", "midt i en sætning")   # ... så der IKKE skiftes
    besked(ui, 22, "Jens", "hej")                 # Jens venter
    ui.root.update()
    assert ui.sidebar is not None, "ingen sideliste i enkelte-tilstand"
    samlet = " ".join(liste_tekster(ui))
    for n in ("Jens", "Anne"):
        assert n in samlet, f"{n} mangler i listen: {samlet!r}"
    assert "Mor" not in samlet, \
        f"den viste samtale står både i hovedet og i listen: {samlet!r}"
    assert "MOR" in ui._top_tekst.cget("text"), "den viste samtale mangler i hovedet"
    assert "F4" in samlet, "F-tasterne står ikke i listen"
    assert "Ny besked" in samlet, "ulæst-markering mangler for Jens"
    luk(ui)


@proev("hver person har sin egen farve — i liste, hoved og bobler")
def _():
    # blink=False: pulsen ved ny besked overmaler topbarens farver i ca. et
    # sekund, og prøven ville ellers ramme midt i den.
    ui = med_tre_personer(blink=False)
    farver = {cid: ui._personfarve(cid) for cid in (11, 22, 33)}
    assert len(set(farver.values())) == 3, f"personer deler farve: {farver}"
    assert ui._kant_ud not in farver.values(), \
        "en person har samme farve som brugerens egne svar"
    # farven skal gå igen på boblen
    besked(ui, 11, "Mor", "farvet boble")
    ui.root.update()
    kanter = [str(r.cget("highlightbackground")) for r in ui.text.winfo_children()]
    assert farver[11] in kanter or ui._accent in kanter, \
        f"boblen bruger ikke personens farve: {kanter}"
    # ... og i navnehovedet — men først når der er kvitteret. Så længe
    # beskeden er ubesvaret, er hovedet rødt, og dét går forud (v4.31).
    assert str(ui._top_tegn.cget("fg")) == lv.FARVE_NY, \
        "tegnet er ikke rødt ved ubesvaret besked"
    ui._select_fkey(0)
    ui.root.update()
    assert str(ui._top_tekst.cget("fg")) == farver[11], "navnet har ikke personens farve"
    # farven skal være den samme efter en genstart (samme whitelist-rækkefølge)
    ui2 = med_tre_personer(blink=False)
    assert {c: ui2._personfarve(c) for c in (11, 22, 33)} == farver, \
        "farverne skifter mellem opstarter"
    luk(ui)
    ui2.root.destroy()


@proev("fællestråd har ingen sideliste — der er kun én samtale")
def _():
    ui = byg(mode="faellestraad")
    assert ui.sidebar is None, "sideliste vist i fællestråd"
    luk(ui)


@proev("listen tegnes ikke om, når intet har ændret sig")
def _():
    # Topbaren opdateres hvert 300. ms. Uden signaturtjek ville hele listen
    # blive bygget om tre gange i sekundet, dagen lang.
    ui = med_tre_personer()
    ui._select_fkey(0)
    ui.root.update()
    foer = [str(w) for w in ui.sidebar.winfo_children()]
    for _ in range(5):
        ui._refresh_topbar()
    ui.root.update()
    assert [str(w) for w in ui.sidebar.winfo_children()] == foer, \
        "listen blev bygget om uden grund"
    ui._select_fkey(1)
    ui.root.update()
    assert [str(w) for w in ui.sidebar.winfo_children()] != foer, \
        "listen blev IKKE tegnet om ved skift"
    luk(ui)
    WHITELIST.write_text("{}")


@proev("statuslinjen under navnet siger, hvad der er sket")
def _():
    ui = med_tre_personer(blink=False)
    besked(ui, 11, "Mor", "hej")
    ui.root.update()
    assert "Ny besked" in ui._top_tekst.cget("text"), \
        f"hovedet siger ikke, at der er en ny besked: {ui.topbar.cget('text')!r}"
    assert status_for(ui, "Jens") == "Ingen beskeder endnu", \
        f"tom samtale: {status_for(ui, 'Jens')!r}"

    besked(ui, 22, "Jens", "hallo")          # inden for ro-tiden -> venter
    ui.root.update()
    assert status_for(ui, "Jens").startswith("Ny besked "), \
        f"ulæst uden klokkeslæt: {status_for(ui, 'Jens')!r}"

    ui._select_fkey(1)                        # besøg Jens
    ui._select_fkey(0)                        # tilbage til Mor
    ui.root.update()
    assert status_for(ui, "Jens").startswith("Læst "), \
        f"efter besøg: {status_for(ui, 'Jens')!r}"

    ui._send_reply("mit svar")
    ui.root.update()
    # Mor er den viste samtale og står derfor i hovedet, ikke i listen
    assert "Du svarede" in ui._top_tekst.cget("text"), \
        f"efter svar: {ui.topbar.cget('text')!r}"
    luk(ui)
    WHITELIST.write_text("{}")


@proev("autosend skifter ikke samtale — brugeren er jo gået fra maskinen")
def _():
    ui, sendte = med_kvitteringsfanger()
    besked(ui, 11, "Mor", "hej")
    ui._select_fkey(0)                       # kvitterer, står hos Mor
    ui.entry.insert("1.0", "halv sætning")
    besked(ui, 22, "Jens", "venter i listen")
    assert ui.selected == 11 and 22 in ui._venter
    ui._last_key = time.monotonic() - (lv.IDLE_RESET_SEC + 1)
    ui._autosend_check()                     # sender af sig selv
    ui.root.update()
    assert ui._kladde() == "", "kladden blev ikke sendt"
    assert ui.selected == 11, "autosend skiftede samtale, uden at nogen så det"
    assert 22 in ui._venter, "den ventende samtale blev ryddet"
    # og et tomt autosend må ALDRIG kvittere på brugerens vegne
    sendte.clear()
    besked(ui, 33, "Anne", "ubesvaret")
    ui._select_fkey(2)
    sendte.clear()
    besked(ui, 33, "Anne", "endnu en ubesvaret")
    ui._last_key = time.monotonic() - (lv.IDLE_RESET_SEC + 1)
    ui._autosend_check()
    ui.root.update()
    assert sendte == [], f"autosend kvitterede med tomt felt: {sendte}"
    luk(ui)


@proev("ALT automatisk kørt samtidig rører kun det, det må")
def _():
    # Den værst tænkelige tilstand: uafsendt tekst i feltet, en ubesvaret
    # besked på skærmen, og en anden samtale der venter. Så køres hver
    # eneste automatiske funktion, og bagefter skal alt stå, som det stod.
    ui, sendte = med_kvitteringsfanger()
    besked(ui, 11, "Mor", "ubesvaret besked")
    besked(ui, 22, "Jens", "venter i listen")
    ui.entry.insert("1.0", "min halve sætning")
    ui._last_key = time.monotonic()          # lige rørt tastaturet
    ui.root.update()

    # NB: fokus sammenlignes før/efter i stedet for at kræve, at det ligger
    # i feltet. I det usynlige skærmmiljø er der ingen vinduesbestyrer til at
    # give fokus — kravet er, at automatikken ikke FLYTTER det.
    foer = (ui.selected, set(ui._venter), set(ui._ukvitteret), ui._kladde(),
            str(ui.root.focus_get()))

    ui._idle_check()          # rul-til-bunden
    ui._autosend_check()      # autosend (må ikke sende — tastetryk er nyt)
    ui._vindue_vagt(3)        # vinduesvagt
    ui._flash(2)              # blink
    ui._refresh_topbar()      # listen og topbaren
    ui._poll_inbox()          # postkassen
    ui.root.update()

    efter = (ui.selected, set(ui._venter), set(ui._ukvitteret), ui._kladde(),
             str(ui.root.focus_get()))
    assert foer == efter, f"automatikken ændrede tilstanden:\n  før:  {foer}\n  efter: {efter}"
    assert sendte == [], f"automatikken sendte noget: {sendte}"
    luk(ui)
    WHITELIST.write_text("{}")


@proev("rød firkant ved ny besked, grønt flueben ved læst")
def _():
    ui = med_tre_personer(blink=False)
    besked(ui, 11, "Mor", "hej")            # Mor vises, ubesvaret
    ui.entry.insert("1.0", "midt i noget")  # ... så Jens ikke henter skærmen
    besked(ui, 22, "Jens", "ny besked")
    ui.root.update()

    tegn_ny, farve_ny = ui._samtaletegn(22)
    assert tegn_ny == "■" and farve_ny == lv.FARVE_NY, (tegn_ny, farve_ny)
    assert "■" in liste_tekster(ui), "den røde firkant ses ikke i listen"

    # den viste samtale er også ubesvaret -> hovedet skal være rødt
    assert ui._top_tegn.cget("text") == "■", ui._top_tegn.cget("text")
    assert str(ui._top_tegn.cget("fg")) == lv.FARVE_NY, \
        "firkanten i hovedet er ikke rød"

    # ... og efter kvittering: grønt flueben og personens egen farve igen
    ui._ryd_kladde()
    ui._select_fkey(0)
    ui.root.update()
    tegn_laest, farve_laest = ui._samtaletegn(11)
    assert tegn_laest == "✓" and farve_laest == lv.FARVE_LAEST
    assert ui._top_tegn.cget("text") == "✓", ui._top_tegn.cget("text")
    assert str(ui._top_tegn.cget("fg")) == lv.FARVE_LAEST, \
        "fluebenet i hovedet er ikke grønt"
    assert str(ui._top_tekst.cget("fg")) == ui._personfarve(11), \
        "navnet blev ikke personens farve igen"
    luk(ui)


@proev("farven er aldrig den eneste oplysning")
def _():
    # Omkring hver tolvte mand kan ikke skelne rød og grøn. Derfor skal
    # både FORM og ORD skille de to tilstande — ellers er skærmen ubrugelig
    # for dem, og det ville vi ikke opdage før hos en kunde.
    ui = med_tre_personer(blink=False)
    besked(ui, 11, "Mor", "hej")
    ui.entry.insert("1.0", "midt i noget")
    besked(ui, 22, "Jens", "ny")
    ui.root.update()
    ny_tegn, _ = ui._samtaletegn(22)
    laest_tegn, _ = ui._samtaletegn(33)
    assert ny_tegn != laest_tegn, "samme tegn til begge tilstande"
    tekster = liste_tekster(ui)
    assert any(x.startswith("Ny besked") for x in tekster), "ordene mangler"
    luk(ui)
    WHITELIST.write_text("{}")


@proev("tegnet står EFTER teksten og har sin egen farve — begge steder")
def _():
    # Fejl i 4.31: tegn og navn lå i samme etiket, så fluebenet arvede
    # personens farve i stedet for den grønne. Tk kan ikke farve dele af
    # én tekst.
    ui = med_tre_personer(blink=False)
    besked(ui, 11, "Mor", "hej")
    ui._select_fkey(0)                       # kvitterer -> grønt flueben
    ui.root.update()
    assert ui._top_tegn.cget("text") == "✓"
    assert str(ui._top_tegn.cget("fg")) == lv.FARVE_LAEST, "fluebenet er ikke grønt"
    assert str(ui._top_tekst.cget("fg")) == ui._personfarve(11), \
        "navnet har ikke personens farve"
    assert "✓" not in ui._top_tekst.cget("text"), "tegnet står stadig inde i teksten"
    # ... og det skal stå LIGE EFTER teksten, ikke ude i højre side.
    # Der måles RELATIVT inde i rammen (winfo_x) og på ØNSKET bredde.
    # Undervejs afslørede netop denne prøve en rigtig fejl: skriftmålingen
    # spurgte programmets første vindue i stedet for sit eget, og skriften
    # blev beregnet til 130 px. Se v4.35.
    ui.root.update_idletasks()
    ui.root.update()
    afstand = ui._top_tegn.winfo_x() - (ui._top_tekst.winfo_x()
                                        + ui._top_tekst.winfo_reqwidth())
    assert -2 <= afstand < 60, f"tegnet står {afstand} px fra teksten"
    assert ui._top_tegn.winfo_x() > ui._top_tekst.winfo_x(), \
        "tegnet står før teksten"
    luk(ui)


@proev("blinket sætter farverne rigtigt igen bagefter")
def _():
    ui = med_tre_personer()      # blink slået til
    besked(ui, 11, "Mor", "hej")
    ui._select_fkey(0)
    ui.root.update()
    ui._flash(0)                 # afslut pulsen
    ui.root.update()
    assert str(ui._top_tegn.cget("fg")) == lv.FARVE_LAEST, \
        "farverne kom ikke tilbage efter blinket"
    assert str(ui.topbar.cget("bg")) == ui._bg, "baggrunden blev hængende"
    luk(ui)
    WHITELIST.write_text("{}")


print("\nKvittering for læst")


@proev("kvittering sendes, når brugeren SELV vælger samtalen")
def _():
    ui, sendte = med_kvitteringsfanger()
    besked(ui, 11, "Mor", "har du set det?")
    assert sendte == [], "kvitterede, bare fordi skærmen viste beskeden"
    ui._select_fkey(0)
    ui.root.update()
    assert len(sendte) == 1, f"ingen kvittering ved valg: {sendte}"
    assert sendte[0][0] == (11,), "kvitteringen gik til den forkerte"
    # I enkelte er én samtale én person — derfor "Din", ikke "Jeres"
    assert lv.KVIT_MAERKE in sendte[0][1], \
        f"kvitteringen bærer ikke øjet: {sendte[0][1]!r}"
    assert "læst" in sendte[0][1].lower(), \
        f"kvitteringen siger ikke, at beskeden er læst: {sendte[0][1]!r}"
    assert "Din" in sendte[0][1], \
        f"enkelte skal sige 'din', ikke 'jeres': {sendte[0][1]!r}"
    # ... og kun én gang
    ui._select_fkey(1)
    ui._select_fkey(0)
    ui.root.update()
    assert len(sendte) == 1, f"kvitterede flere gange for samme besked: {sendte}"
    luk(ui)


@proev("svarer hun, er svaret selv kvitteringen — ingen ekstra besked")
def _():
    ui, sendte = med_kvitteringsfanger()
    besked(ui, 33, "Anne", "kommer du?")
    ui._select_fkey(2)          # vælger Anne -> kvitterer
    ui.root.update()
    sendte.clear()
    besked(ui, 33, "Anne", "hallo?")
    ui._send_reply("ja jeg kommer")
    ui.root.update()
    kvitteringer = [x for x in sendte if lv.KVIT_MAERKE in x[1]]
    assert kvitteringer == [], f"sendte kvittering oveni svaret: {kvitteringer}"
    assert 33 not in ui._ukvitteret, "beskeden står stadig som ubesvaret"
    luk(ui)
    WHITELIST.write_text("{}")


@proev("er der kun én person, forsvinder listen og giver plads til beskederne")
def _():
    WHITELIST.write_text(json.dumps({"11": "Mor"}))
    ui = byg(mode="enkelte")
    ui.whitelist = lv.Whitelist(WHITELIST)
    ui.bot.whitelist = ui.whitelist
    besked(ui, 11, "Mor", "hej")
    ui.root.update()
    assert not ui.sidebar.winfo_ismapped(), "tom liste optager plads"
    assert "MOR" in ui._top_tekst.cget("text")
    # ... og kommer der en person mere, dukker listen op igen
    WHITELIST.write_text(json.dumps({"11": "Mor", "22": "Jens"}))
    ui.whitelist = lv.Whitelist(WHITELIST)
    ui.bot.whitelist = ui.whitelist
    ui._refresh_topbar()
    ui.root.update()
    assert ui.sidebar.winfo_ismapped(), "listen kom ikke frem igen"
    assert "Jens" in " ".join(liste_tekster(ui))
    luk(ui)
    WHITELIST.write_text("{}")


@proev("et sendt svar bliver stående — også uden valgt samtale")
def _():
    # Mistænkt årsag til "den viser ikke altid, at jeg har sendt noget":
    # svaret gemmes under den, der skrev sidst, mens skærmen filtrerer på
    # den valgte. Boblen kunne ses et øjeblik og forsvinde igen.
    ui = med_tre_personer()
    besked(ui, 11, "Mor", "hej")
    ui.selected = None                      # ingen valgt samtale
    ui._send_reply("mit svar")
    ui.root.update()
    assert ui.selected == 11, "svaret satte ikke den viste samtale"
    assert "mit svar" in paa_skaermen(ui)
    ui._tegn_samtale()                      # gentegning må ikke fjerne det
    ui.root.update()
    assert "mit svar" in paa_skaermen(ui), "svaret forsvandt ved gentegning"
    luk(ui)
    WHITELIST.write_text("{}")


# ------------------------------------------------------------ vinduesvagten
print("\nNattetilstand")


@proev("skærmen er sort om natten og tændt om dagen")
def _():
    # MASKINEN SLUKKER IKKE LÆNGERE. Prøvet på hardware: den kunne slet
    # ikke vækkes af urets alarm, og lå derfor slukket hele dagen efter.
    # I stedet bliver skærmen sort — og en maskine, der kører, kan
    # genstarte sig selv, hvilket en slukket ikke kan.
    from datetime import datetime as dt
    ui = byg()
    try:
        for time_, forventet in ((22, True), (23, True), (3, True),
                                 (7, True), (8, False), (14, False),
                                 (21, False)):
            naar = dt(2026, 8, 15, time_, 30)
            assert ui._er_nat(naar) is forventet, (
                f"kl. {time_}: fik {ui._er_nat(naar)}, ventede {forventet}")
        # perioden går hen over midnat — det er den, der plejer at gå galt
        assert ui._er_nat(dt(2026, 8, 15, 0, 1)) is True, "midnat regnes som dag"
    finally:
        luk(ui)


@proev("maskinen tier om natten — ingen startbesked kl. 3")
def _():
    # Maskinen genstarter kl. 03 for at få en frisk start. Uden dette ville
    # den sende "✅ startede" til administrators telefon HVER NAT kl. 3.
    # Fejlen ville vi selv have lavet ved at flytte nedlukningen.
    b = bot({})
    from datetime import datetime as dt
    assert b._er_nat(dt(2026, 8, 15, 3, 0)) is True, "kl. 3 regnes ikke som nat"
    assert b._er_nat(dt(2026, 8, 15, 9, 0)) is False, "kl. 9 regnes som nat"
    # bot-laget og skærmen skal være enige om, hvad nat er
    ui = byg()
    try:
        for t in (0, 3, 7, 8, 12, 21, 22, 23):
            naar = dt(2026, 8, 15, t, 0)
            assert ui._er_nat(naar) == b._er_nat(naar), \
                f"skærm og bot er uenige om kl. {t}"
    finally:
        luk(ui)


@proev("kun ÉN planlagt besked om dagen")
def _():
    # Der var før fem: en startbesked plus et heartbeat hver sjette time.
    # Med ti maskiner er det halvtreds beskeder om dagen — og en alarm,
    # ingen læser, er ikke en alarm. Nu kommer status én gang kl. 8,
    # sammen med morgenens livstegn.
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    assert "HEARTBEAT_INTERVAL" not in kilde, \
        "heartbeat-løkken er der stadig — så bliver det fem beskeder om dagen"
    assert "_heartbeat_loop" not in kilde, "heartbeat-løkken er der stadig"
    # ... og morgenbeskeden skal indeholde statussen, ikke bare et livstegn
    assert "_status_text()" in kilde.split("skærmen er tændt")[0] or \
           'send_admin("☀️ " + self.bot._status_text())' in kilde, \
        "morgenbeskeden indeholder ikke maskinens status"


@proev("nattetæppet dækker hele skærmen og ligger nederst om dagen")
def _():
    ui = byg()
    try:
        ui.root.geometry(f"{ui.root.winfo_screenwidth()}x"
                         f"{ui.root.winfo_screenheight()}+0+0")
        ui.root.update()
        ui.root.update_idletasks()
        t = ui._nat_taeppe
        assert t.winfo_width() >= ui.root.winfo_screenwidth() - 2, \
            f"tæppet dækker kun {t.winfo_width()} af {ui.root.winfo_screenwidth()} px"
        assert str(t.cget("bg")) in ("#000000", "black"), t.cget("bg")
        # om dagen skal det ligge under alt andet
        soesken = ui.root.winfo_children()
        assert soesken.index(t) == 0, \
            "tæppet ligger ikke nederst — så dækker det skærmen om dagen"
    finally:
        luk(ui)


print("\nVinduesvagt")


@proev("vagten sætter vinduet øverst hver gang — den måler ikke længere")
def _():
    # v4.29 spurgte "er vinduet synligt" og greb kun ind, hvis ikke. I drift
    # meldte den derfor kun én gang ved opstart, mens skærmen resten af
    # dagen viste skrivebordet: winfo_viewable() betyder TEGNET, ikke ØVERST.
    #
    # NB: prøven kontrollerer, at vagten BEDER om -topmost. Uden en
    # vinduesbestyrer i det usynlige skærmmiljø svarer X altid 0 tilbage,
    # uanset hvad der blev sat — attributten håndhæves af skrivebordet.
    ui = byg()
    kaldt = []
    rigtig = ui.root.attributes

    def spion(*a):
        kaldt.append(a)
        return rigtig(*a)
    ui.root.attributes = spion
    for n in (0, 1, 50):
        ui._vindue_vagt(n)
    ui.root.update()
    topmost = [a for a in kaldt if a and a[0] == "-topmost" and a[1:] == (True,)]
    assert len(topmost) == 3, \
        f"vinduet blev ikke sat øverst hver gang: {kaldt}"
    fuld = [a for a in kaldt if a and a[0] == "-fullscreen"]
    assert len(fuld) == 3, f"fuldskærm blev ikke sat hver gang: {kaldt}"
    ui.root.attributes = rigtig
    # et skjult vindue hentes stadig frem
    ui.root.withdraw()
    ui.root.update()
    ui._vindue_vagt(99)
    ui.root.update()
    assert ui.root.winfo_viewable(), "vagten hentede ikke vinduet frem"
    luk(ui)
    ui._vindue_vagt(0)          # må ikke vælte, når vinduet er lukket


@proev("vagten holder ALDRIG pause — et vindue foran er altid en fejl")
def _():
    # Her stod to prøver om en videoafspiller, der måtte have skærmen.
    # Video er fjernet i v4.74: mpv tog både skærmen OG tastaturet, så
    # Q lukkede videoen i stedet for at sende "Tak". En tast, der skifter
    # betydning, er værre end en funktion, der mangler.
    #
    # Dermed findes der ikke længere et lovligt vindue foran Livline.
    # Vagten skal altid slå sig frem — uden undtagelser at gætte om.
    ui = byg()
    try:
        kaldt = []
        rigtig = ui.root.attributes
        ui.root.attributes = lambda *a: (kaldt.append(a), rigtig(*a))[1]
        ui._vindue_vagt(3)
        ui.root.update()
        assert [a for a in kaldt if a[:2] == ("-topmost", True)], \
            "vagten slog sig ikke frem"
        ui.root.attributes = rigtig
    finally:
        luk(ui)
    # Ingen afspiller må kunne holde vagten væk
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    vagt = kilde.split("def _vindue_vagt")[1].split("def ")[0]
    kode = "\n".join(l for l in vagt.splitlines()
                     if not l.lstrip().startswith("#"))
    assert "return" not in kode.split("try:")[0], \
        "vagten har fået en undtagelse igen — så kan et vindue blive stående"


@proev("video vises ikke, og afsenderen får det at vide")
def _():
    # Video blev fjernet, fordi afspilleren kaprede tastaturet. Men en
    # video, der bare forsvandt, ville være værre: afsenderen ville tro,
    # den var set. Derfor skal hun have svar — og de øvrige i tråden skal
    # have selve videoen på deres telefoner.
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    gren = kilde.split("elif msg.video or msg.video_note:")[1].split("else:")[0]
    assert "_download" not in gren, \
        "videoen hentes stadig ned — filen fylder, og der er intet at bruge den til"
    assert "reply_text" in gren, "afsenderen får ikke at vide, at video ikke vises"
    assert "ikke vises på" in gren and "Livline-skærmen" in gren, \
        "svaret siger ikke, at det er SKÆRMEN der ikke kan — ikke ham"
    assert "kan desværre ikke vises her" in gren, \
        "linjen på skærmen siger ikke, hvorfor videoen ikke kommer — " \
        "så sidder han og venter på, at den begynder"
    assert "_rebroadcast" in gren, \
        "de øvrige i tråden får ikke videoen på deres telefoner"


@proev("talebeskeder afspilles ikke — og afsenderen får det at vide")
def _():
    # SAMME BESLUTNING SOM VIDEO, truffet samme dag. En talebesked
    # starter af sig selv, kan ikke standses med de otte taster, og kl. 2
    # om natten fylder den hele lejligheden. Dertil bruges høreapparater
    # i den aldersgruppe — telefonen gør arbejdet bedre end en højttaler
    # i en stue. Men den må ikke bare forsvinde: afsenderen skal have
    # svar, og de øvrige skal have den ægte besked på telefonen.
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    gren = kilde.split("elif msg.voice or msg.audio:")[1].split(
        "elif msg.video")[0]
    assert "_download" not in gren, \
        "talebeskeden hentes stadig ned — der er intet at bruge filen til"
    assert "reply_text" in gren, \
        "afsenderen får ikke at vide, at talebeskeden ikke afspilles"
    assert "ikke afspilles" in gren and "Livline-skærmen" in gren, \
        "svaret siger ikke, at det er SKÆRMEN der ikke kan"
    assert "kan desværre ikke vises her" in gren, \
        "linjen på skærmen siger ikke, hvorfor der ikke kommer lyd — " \
        "så sidder han og venter på, at den begynder"
    assert "_rebroadcast" in gren, \
        "de øvrige i tråden får ikke talebeskeden på deres telefoner"


@proev("maskinen laver ALDRIG lyd")
def _():
    # Bippet var det sidste, der kunne vække nogen. Skærmen blev sort
    # kl. 22, men lyden gjorde ikke: skrev barnebarnet kl. 01.30, bippede
    # maskinen i stuen. Der er ingen at skrue ned for den — han har otte
    # taster, og ingen af dem er lydstyrke.
    #
    # At der er en ny besked, siges nu kun med øjnene: det røde ■ i
    # hovedet og et kort blink i kanten. Begge dele synlige på afstand,
    # ingen af dem i stand til at vække nogen.
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    kode = "\n".join(l for l in kilde.splitlines()
                     if not l.lstrip().startswith("#"))
    for forbudt in ("bell(", "mpv", "Popen([\"mpv", "aplay", "paplay",
                    "playsound", "winsound"):
        assert forbudt not in kode, \
            f"maskinen kan stadig lave lyd: {forbudt!r} står i koden"
    # … og den skal stadig sige til med øjnene
    ui = byg(mode="faellestraad")
    try:
        besked(ui, 11, "Mor", "er du vågen?")
        ui.root.update()
        assert "er du vågen" in paa_skaermen(ui), "beskeden kom slet ikke frem"
        # Hvad ØJET får i stedet for lyden. I fællestråd er det hovedet,
        # der bærer beskeden: hvad der er sket, og hvornår. Den røde ■
        # hører til sidelisten, som fællestråd ikke har — derfor skal
        # hovedet kunne stå alene.
        hoved = ui._top_tekst.cget("text")
        assert "Ny besked" in hoved and re.search(r"\d\d[.:]\d\d", hoved), \
            f"ingen lyd OG intet i hovedet — så siger maskinen intet: {hoved!r}"
    finally:
        luk(ui)


@proev("vagten flytter ikke markøren, mens brugeren skriver")
def _():
    ui = byg()
    ui.entry.focus_force()
    ui.root.update()
    foer = str(ui.root.focus_get())
    for n in range(4):
        ui._vindue_vagt(n)
    ui.root.update()
    assert str(ui.root.focus_get()) == foer, "vagten flyttede fokus"
    luk(ui)


# ------------------------------------------------------------------ botten
print("\nBot og godkendelse")




@proev("godkend-knappen tilføjer personen — og kun for administrator")
def _():
    b = bot({})
    b._afventer[8792215151] = "Test pc"
    redigeret, sendte = [], []

    class Q:
        def __init__(self, fra):
            self.data, self.from_user = "godkend:8792215151", types.SimpleNamespace(id=fra)

        async def answer(self):
            pass

        async def edit_message_text(self, t, **k):
            redigeret.append(t)

    class B:
        async def send_message(self, cid, t, **k):
            sendte.append(cid)

    ctx = types.SimpleNamespace(bot=B())
    asyncio.run(b._on_godkend(types.SimpleNamespace(callback_query=Q(999)), ctx))
    assert b.whitelist.ids() == [], "en fremmed kunne godkende"
    asyncio.run(b._on_godkend(types.SimpleNamespace(callback_query=Q(1)), ctx))
    assert b.whitelist.ids() == [8792215151], b.whitelist.ids()
    assert json.loads(WHITELIST.read_text()), "ikke gemt på disk"
    assert sendte == [8792215151], "personen fik ingen bekræftelse"


@proev("maskinen advarer, hvis administrator selv står på whitelisten")
def _():
    assert "Privatliv" in bot({"1": "Ulrik", "77": "Mette"})._privatlivsadvarsel()
    assert bot({"77": "Mette"})._privatlivsadvarsel() == ""
    assert bot({"1": "Ulrik"}, mode="enkelte")._privatlivsadvarsel() == "", \
        "advarer i enkelte-tilstand, hvor beskeder ikke videresendes"


@proev("alle kommando-handlere registreres, også knappen")
def _():
    for n in ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy",
              "HTTPS_PROXY", "https_proxy"):
        os.environ.pop(n, None)      # sandkassens proxy forstyrrer ellers PTB
    app = bot({})._build_app()
    navne = [type(h).__name__ for grp in app.handlers.values() for h in grp]
    assert "CallbackQueryHandler" in navne, "godkend-knappen mangler en handler"
    assert "CommandHandler" in navne and "MessageHandler" in navne

    # HVER kommando skal have en handler. Prøven så før kun EFTER, at der
    # fandtes mindst én CommandHandler — og /start manglede i månedsvis,
    # mens både install.sh og byggevejledningen bad familien om at bruge
    # den. Trykkede de Start, skete der intet. At tælle er ikke at tjekke.
    kommandoer = set()
    for grp in app.handlers.values():
        for h in grp:
            kommandoer |= set(getattr(h, "commands", ()) or ())
    for k in ("start", "status", "tilfoej", "fjern", "liste",
              "opdater", "skaerm", "indstillinger", "hjaelp"):
        assert k in kommandoer, f"/{k} har ingen handler — den gør ingenting"


def falsk_besked(**felter):
    """En Telegram-besked, hvor alt er tomt undtagen det, prøven sætter."""
    tom = dict(text=None, photo=None, voice=None, video=None, video_note=None,
               sticker=None, animation=None, document=None, audio=None,
               caption=None)
    tom.update(felter)
    return types.SimpleNamespace(**tom)


class FalskBot:
    """Skriver ned, hvad der blev kaldt, i stedet for at sende noget."""

    def __init__(self):
        self.kald = []

    def __getattr__(self, navn):
        async def kald(*a, **kw):
            self.kald.append((navn, a, kw))
        return kald


@proev("i fællestråd får de andre ALT — også GIF'er og klistermærker")
def _():
    # Her stod et return: skærmen fik sin linje "(Emil sendte en GIF)", men
    # de ØVRIGE i tråden fik ingenting og anede ikke, at der havde været
    # kontakt. Telefonerne kan godt vise en GIF, selvom skærmen ikke kan.
    w = bot({"111": "Emil", "222": "Mette"})
    fb = FalskBot()
    w.app = types.SimpleNamespace(bot=fb)

    for felt, forventet in (("sticker", "send_sticker"),
                            ("animation", "send_animation"),
                            ("document", "send_document"),
                            ("audio", "send_audio"),
                            ("photo", "send_photo"),
                            ("voice", "send_voice")):
        fb.kald.clear()
        vaerdi = ([types.SimpleNamespace(file_id="F")] if felt == "photo"
                  else types.SimpleNamespace(file_id="F"))
        asyncio.run(w._rebroadcast(falsk_besked(**{felt: vaerdi}),
                                   "Emil", exclude=111))
        assert [k[0] for k in fb.kald] == [forventet], \
            f"{felt} blev ikke sendt videre: {fb.kald}"

    # Noget, vi ikke har en knap til (kort, kontaktkort): hellere en linje
    # for lidt end tavshed
    fb.kald.clear()
    asyncio.run(w._rebroadcast(falsk_besked(location=object()),
                               "Emil", exclude=111))
    assert fb.kald and fb.kald[0][0] == "send_message", \
        f"en ukendt beskedtype forsvandt i tavshed: {fb.kald}"

    # En video, der var for stor: der er intet at sende videre, men de
    # andre skal stadig vide, at der HAR været kontakt
    fb.kald.clear()
    asyncio.run(w._rebroadcast(
        falsk_besked(video=types.SimpleNamespace(file_id="F")),
        "Emil", exclude=111, note="sendte en video, der var for stor"))
    assert fb.kald[0][0] == "send_message", "sendte videoen i stedet for beskeden"
    assert "for stor" in fb.kald[0][1][1], f"linjen mangler: {fb.kald[0]}"


@proev("en sticker standser ikke, før de andre har fået den")
def _():
    # Selve returnet, der var fejlen. En prøve på opførsel kan ikke se det,
    # fordi grenen ligger midt i beskedhåndteringen — så vi læser koden.
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    gren = kilde.split('"en sticker" if msg.sticker')[1].split(
        "async def _rebroadcast")[0]
    efter = gren.split("_modtag(")[1].split("_rebroadcast")[0]
    linjer = [l.strip() for l in efter.splitlines()
              if l.strip() and not l.strip().startswith("#")]
    assert "return" not in linjer, \
        "grenen standser stadig, før de øvrige i tråden får noget"


@proev("en fejlet genudsendelse bliver også sagt højt")
def _():
    # Genudsendelsen brugte bot'en direkte og slugte fejl i en log.warning.
    # En blokeret modtager forsvandt derfor lydløst ud af familiens samtale.
    w = bot({"111": "Emil", "222": "Mette"})
    meldinger = []

    async def send_message(chat_id=None, text=None, *a, **kw):
        meldinger.append((chat_id, text))

    async def send_sticker(*a, **kw):
        raise RuntimeError("Forbidden: bot was blocked by the user")

    w.app = types.SimpleNamespace(bot=types.SimpleNamespace(
        send_message=send_message, send_sticker=send_sticker))
    asyncio.run(w._rebroadcast(
        falsk_besked(sticker=types.SimpleNamespace(file_id="F")),
        "Emil", exclude=111))
    assert meldinger, "genudsendelsen fejlede i tavshed"
    assert meldinger[0][0] == w.config.admin_chat_id, \
        "advarslen gik ikke til administrator"
    assert "Mette" in meldinger[0][1], f"navnet mangler: {meldinger[0][1]!r}"


@proev("en besked, der ikke nåede frem, bliver sagt højt")
def _():
    # Den tavseste fejl i maskinen: afsendelsen melder "det gik godt", hvis
    # bare ÉN modtager fik beskeden. SET I DRIFT: en pårørende kan blokere
    # botten i Telegram. Så får hun ingen beskeder fra sin far, opdager det
    # ikke — der kommer jo bare ingenting — og han tror, hun ikke skriver.
    w = bot({"111": "Mette"})
    sendt = []

    async def falsk_send(chat_id=None, text=None, **_):
        sendt.append((chat_id, text))

    w.app = types.SimpleNamespace(
        bot=types.SimpleNamespace(send_message=falsk_send))
    fejl = RuntimeError("Forbidden: bot was blocked by the user")

    asyncio.run(w._meld_afsendelsesfejl(111, fejl))
    assert len(sendt) == 1, "administrator fik ingen advarsel"
    assert sendt[0][0] == w.config.admin_chat_id, "advarslen gik til den forkerte"
    assert "Mette" in sendt[0][1], f"navnet mangler i advarslen: {sendt[0][1]!r}"
    assert "blokeret" in sendt[0][1].lower(), \
        "advarslen siger ikke, hvad man typisk skal gøre"

    # Kun én gang: en telefon, der er slukket i en uge, må ikke fylde skærmen
    asyncio.run(w._meld_afsendelsesfejl(111, fejl))
    assert len(sendt) == 1, "samme person blev meldt flere gange"

    # … men når det har virket igen, skal en NY fejl kunne meldes
    w._send_fejl.discard(111)            # det send_text gør ved held
    asyncio.run(w._meld_afsendelsesfejl(111, fejl))
    assert len(sendt) == 2, "kunne ikke melde igen, efter det havde virket"

    # Administrator må ALDRIG meldes: fejlen ville forsøge at melde sig selv
    asyncio.run(w._meld_afsendelsesfejl(w.config.admin_chat_id, fejl))
    assert len(sendt) == 2, "forsøgte at melde en fejl til den, fejlen handler om"


@proev("en vellykket afsendelse nulstiller fejlmeldingen")
def _():
    # Uden nulstillingen ville en person, der engang var uopnåelig, aldrig
    # blive meldt igen — heller ikke når hun blokerer botten et år senere.
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    krop = kilde.split("async def send_alle")[1].split("return ok")[0]
    assert "_send_fejl.discard" in krop, \
        "fejlmeldingen nulstilles ikke, når afsendelsen lykkes igen"
    assert "_meld_afsendelsesfejl" in krop, \
        "en fejlet afsendelse meldes ikke videre"


@proev("/start er ÅBEN for fremmede — det er hele dens formål")
def _():
    # De øvrige kommandoer er kun for administrator. /start er den ENE,
    # en fremmed skal kunne bruge: den er måden, man beder om adgang på.
    # Får den et admin-filter, kan ingen familie komme med — og fejlen
    # ville vise sig stående i deres stue.
    for n in ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy",
              "HTTPS_PROXY", "https_proxy"):
        os.environ.pop(n, None)
    app = bot({})._build_app()
    for grp in app.handlers.values():
        for h in grp:
            if "start" in (getattr(h, "commands", ()) or ()):
                assert h.filters is None or "Chat" not in repr(h.filters), \
                    "/start er låst til administrator — så kan ingen bede om adgang"
                return
    raise AssertionError("fandt ingen handler for /start")


# ------------------------------------------------------------------ config
print("\nConfig")


@proev("stavefejl i config meldes som ukendt felt")
def _():
    d = json.loads(CONFIG.read_text())
    d["tastar"] = ["a"]                       # klassisk tastefejl for "taster"
    fejl_config = ARBEJDE / "stavefejl.json"
    fejl_config.write_text(json.dumps(d, ensure_ascii=False))
    # NB: stien gives som argument. Config.load() binder CONFIG_PATH som
    # standardværdi ved definitionen, så det nytter ikke at ændre variablen
    # bagefter — en fælde, denne prøve selv gik i første gang.
    assert "tastar" in lv.Config.load(fejl_config).ukendte


@proev("skrivefelt og faste svar udelukker hinanden")
def _():
    c = lv.Config.load()
    assert c.text_input and not c.replies, \
        "faste svar findes i skrivefelt-tilstand — tasterne kan kollidere"


# ------------------------------------------------------------------ tråde
# Alt her handler om det samme: appen har TO tråde — bot-tråden henter fra
# Telegram, hovedtråden tegner. Tkinter må kun røres fra hovedtråden, og
# filer, begge skriver i, skal beskyttes. Fejl af den slags viser sig
# sjældent, tilfældigt og aldrig mens man kigger.
print("\nTråde og delte filer")


@proev("resultatet af en afsendelse rører ikke Tkinter fra en anden tråd")
def _():
    # Fejl fundet ved gennemgang før genopbygningen: svaret fra Telegram
    # kommer i en timer-tråd, og det gamle tilbagekald tegnede DIREKTE i
    # boblen derfra. Nu skal det gå gennem en kø, som hovedtråden tømmer.
    ui = med_tre_personer(blink=False)
    fanget = {}
    ui.bot.send_text = lambda ids, tekst, svar=None: fanget.update(svar=svar)
    besked(ui, 11, "Mor", "hej")
    ui._select_fkey(0)
    ui._send_reply("mit svar")
    ui.root.update()
    assert fanget.get("svar") is not None, "der blev ikke bedt om svar"

    traad_fejl = []

    def i_anden_traad():
        try:
            fanget["svar"](False)        # præcis som timer-tråden gør
        except Exception as e:
            traad_fejl.append(e)
    t = threading.Thread(target=i_anden_traad)
    t.start(); t.join(5)
    assert not traad_fejl, f"tilbagekaldet væltede i en anden tråd: {traad_fejl}"
    assert not ui._svarkoe.empty(), "resultatet endte ikke i køen"

    # ... og hovedtråden henter det og markerer boblen
    ui._poll_inbox()
    ui.root.update()
    assert ui._svarkoe.empty(), "køen blev ikke tømt"
    advarsler = [x for x in paa_skaermen(ui).splitlines()
                 if "Kunne ikke sendes" in x]
    assert advarsler, "boblen blev ikke markeret som mislykket"
    luk(ui)
    WHITELIST.write_text("{}")


@proev("to tråde kan skrive i historikken uden at tabe beskeder")
def _():
    # Bot-tråden gemmer indgående beskeder, UI-tråden gemmer brugerens egne
    # svar — begge som læs-ret-skriv af HELE filen. Uden lås kan den ene
    # skrive oven i den andens: en besked, der stod på skærmen, er væk
    # efter næste genstart.
    sti = ARBEJDE / "historik-traade.json"
    sti.unlink(missing_ok=True)
    antal = 60

    def skriv(start, egen):
        for i in range(start, start + antal):
            lv.gem_i_historik(sti, lv.Incoming(
                "Prøve", 11, "text", text=f"besked {i}"), egen=egen)

    a = threading.Thread(target=skriv, args=(0, False))
    b = threading.Thread(target=skriv, args=(1000, True))
    a.start(); b.start(); a.join(30); b.join(30)

    rows = json.loads(sti.read_text(encoding="utf-8"))
    assert len(rows) == lv.HISTORY_MAX, \
        f"historikken holdt ikke sin grænse: {len(rows)}"
    # Begge tråde skal være repræsenteret i de sidste 100 — er låsen væk,
    # overskriver den ene systematisk den anden.
    fra_a = sum(1 for r in rows if not r["egen"])
    fra_b = sum(1 for r in rows if r["egen"])
    assert fra_a and fra_b, \
        f"den ene tråds beskeder forsvandt helt (a={fra_a}, b={fra_b})"
    # ... og ingen post må være halvskrevet
    for r in rows:
        assert set(r) >= {"navn", "chat_id", "tekst", "tid", "egen"}, r


@proev("ventetiden på svar fra Telegram har et loft")
def _():
    # Uden loft ville en død forbindelse give en ny timer-tråd hvert halve
    # sekund, resten af dagen.
    assert lv.SEND_SVAR_FORSOEG > 0
    assert lv.SEND_SVAR_FORSOEG <= 240, \
        f"venter {lv.SEND_SVAR_FORSOEG // 2} sek. på et svar — for længe"


print("\nTemaer")


@proev("hvert tema, koden nævner, findes også")
def _():
    # Kommentaren over THEMES lovede sort, moerk, lys og gul. De findes
    # ikke, og et ukendt tema faldt STILLE tilbage til "varm" — maskinen
    # så rigtig ud og gjorde noget andet. Samme fejltype som
    # "betjening: begge", bare tavs.
    import re
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    kom = kilde[kilde.index("# Farvetemaer"):kilde.index("THEMES = {")]
    # linjer i formen "#   navn   beskrivelse" — kun de indrykkede
    lovet = set(re.findall(r"^#\s{3}(\w+)\s{2,}", kom, re.M))
    mangler = lovet - set(lv.THEMES)
    assert not mangler, f"kommentaren lover temaer, der ikke findes: {mangler}"


@proev("et ukendt tema siges højt i stedet for at falde stille tilbage")
def _():
    ui = byg(theme="findes-ikke")
    try:
        assert ui._bg == lv.THEMES["varm"]["bg"], "faldt ikke tilbage til varm"
    finally:
        luk(ui)
    # ... og /indstillinger skal sige det højt
    assert bot({}, theme="findes-ikke")._tema_note(), \
        "/indstillinger advarer ikke om et ukendt tema"
    assert bot({}, theme="varm")._tema_note() == "", \
        "advarer om et tema, der findes"


print("\nGenvejstaster (trykkes rigtigt, ikke kaldt direkte)")


def _med_taster(taster, svar, **ekstra):
    d = json.loads(CONFIG.read_text())
    d.update(betjening="knapper", svar=svar, taster=taster, **ekstra)
    sti = ARBEJDE / "config-taster.json"
    sti.write_text(json.dumps(d, ensure_ascii=False))
    ui = lv.LivlineUI(lv.Config.load(sti))
    ui.root.geometry(f"{ui.root.winfo_screenwidth()}x"
                     f"{ui.root.winfo_screenheight()}+0+0")
    ui.root.update()
    sendt = []
    ui._send_reply = sendt.append
    return ui, sendt


@proev("taltasterne 1/2/3 sender — og et museklik gør IKKE")
def _():
    # FUNDET PÅ RIGTIG HARDWARE, ikke i prøverne: bindingen hed "<1>", og i
    # Tk betyder <1> MUSEKNAP 1 — ikke tallet. Taltasterne virkede derfor
    # aldrig, mens et klik hvor som helst på skærmen sendte en besked.
    # <2> er midterklik og <3> højreklik, så alle tre svar kunne udløses
    # med musen alene. På en kommende touch-maskine ville det have været
    # umuligt at bruge.
    #
    # Fejlen overlevede, fordi de maskiner, der var i drift, havde
    # BOGSTAVER i "taster" — og bogstaver er ikke tvetydige i Tk.
    # Prøverne ramte den ikke, fordi de kaldte _send_reply direkte i
    # stedet for at trykke på tasten. Derfor trykkes der rigtigt her.
    ui, sendt = _med_taster(["1", "2", "3"], ["Et", "To", "Tre"])
    try:
        for tast, forventet in (("1", "Et"), ("2", "To"), ("3", "Tre")):
            sendt.clear()
            ui.root.event_generate(f"<KeyPress-{tast}>", when="now")
            ui.root.update()
            assert sendt == [forventet], \
                f"tasten {tast} sendte {sendt} i stedet for [{forventet!r}]"

        # ... og musen må ALDRIG sende noget
        for knap in (1, 2, 3):
            sendt.clear()
            ui.root.event_generate(f"<Button-{knap}>", when="now")
            ui.root.update()
            assert sendt == [], \
                f"museknap {knap} sendte en besked: {sendt}"
    finally:
        luk(ui)


@proev("bogstavtaster virker — også med Caps Lock og danske tegn")
def _():
    ui, sendt = _med_taster(["a", "c", "æ/ae"], ["Alt godt", "Ring", "Æblekage"])
    try:
        for tast, forventet in (("a", "Alt godt"), ("A", "Alt godt"),
                                ("c", "Ring"), ("C", "Ring")):
            sendt.clear()
            ui.root.event_generate(f"<KeyPress-{tast}>", when="now")
            ui.root.update()
            assert sendt == [forventet], \
                f"tasten {tast} sendte {sendt}, ventede [{forventet!r}]"
        # æ bindes gennem KEYSYM-tabellen til "ae". Her kontrolleres KUN, at
        # bindingen findes — ikke at den kan trykkes. Det usynlige skærmmiljø
        # kører amerikansk tastaturlayout, hvor tegnet ikke findes, så et
        # syntetisk tryk når aldrig frem. På en dansk maskine gør det.
        bindinger = ui.root.bind()
        assert "<Key-ae>" in bindinger, \
            f"æ blev ikke bundet gennem KEYSYM: {bindinger}"
    finally:
        luk(ui)


@proev("ingen tastebinding må kunne forveksles med en museknap")
def _():
    # Generelt værn: enhver binding, der er et rent tal i vinkelparenteser,
    # er en museknap. Den fejl skal ikke kunne komme igen ad en anden vej.
    ui, _ = _med_taster(["1", "2", "3"], ["Et", "To", "Tre"])
    try:
        for b in ui.root.bind():
            assert not re.fullmatch(r"<\d+>", b), \
                f"bindingen {b} er en museknap, ikke en tast"
    finally:
        luk(ui)


print("\nKoden må ikke love noget, den ikke kan")


@proev("hver værdi, docstringen nævner for mode og betjening, kan bruges")
def _():
    # Fundet ved en udefrakommende gennemgang: docstringen sagde
    # "betjening (knapper | tastatur | begge)". "begge" findes ikke —
    # Config.load kaster ValueError, appen starter ikke, og run.sh ville
    # prøve rollback forgæves, fordi fejlen sad i CONFIG, ikke i koden.
    # En maskine sat op efter sin egen dokumentation ville altså være død,
    # og sikkerhedsnettet magtesløst.
    import re
    doc = lv.__doc__ or ""
    grund = json.loads(CONFIG.read_text())
    for felt in ("mode", "betjening"):
        m = re.search(rf'"{felt}" i config \(([^)]+)\)', doc)
        if not m:
            continue
        for vaerdi in [x.strip() for x in m.group(1).split("|")]:
            sti = ARBEJDE / f"doc-{felt}-{vaerdi}.json"
            sti.write_text(json.dumps({**grund, felt: vaerdi},
                                      ensure_ascii=False))
            try:
                lv.Config.load(sti)
            except Exception as e:
                raise AssertionError(
                    f'docstringen nævner "{felt}": "{vaerdi}", men '
                    f"config afviser den: {e}")


@proev("docstringen anbefaler ikke længere --break-system-packages")
def _():
    # Den stod som installationsvejledning i selve programmet, længe efter
    # at install.sh var gået over til et virtuelt miljø. Et menneske, der
    # fulgte den, ville genindføre præcis den fælde, vi lige havde fjernet.
    doc = lv.__doc__ or ""
    for linje in doc.splitlines():
        if "--break-system-packages" in linje and "ALDRIG" not in linje:
            raise AssertionError(f"docstringen anbefaler stadig flaget: {linje.strip()}")


@proev("alle kommandoer i docstringen findes også i botten")
def _():
    import re
    doc = lv.__doc__ or ""
    # (?![/\w]) holder stier ude: "/opt/livline/venv/bin/pip" er ikke en
    # kommando. Prøven fandt selv fælden første gang den kørte.
    nævnt = set(re.findall(r"^\s{4}/(\w+)(?![/\w])", doc, re.M))
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    findes = set(re.findall(r'CommandHandler\("(\w+)"', kilde))
    mangler = nævnt - findes
    assert not mangler, f"docstringen lover kommandoer, der ikke findes: {mangler}"


print("\nSigneret /opdater")


def _noegler():
    """Laver et engangs-nøglepar til prøven. openssl findes på maskinen,
    fordi install.sh installerer den."""
    hem = ARBEJDE / "test.key"
    pub = ARBEJDE / "test.pub"
    if not pub.exists():
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA",
                        "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(hem)],
                       check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(hem), "-pubout",
                        "-out", str(pub)],
                       check=True, capture_output=True)
    return hem, pub


def _signer(hem, tekst: str) -> bytes:
    f = ARBEJDE / "signeret.txt"
    sig = ARBEJDE / "signeret.sig"
    f.write_text(tekst, encoding="utf-8")
    subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(hem),
                    "-out", str(sig), str(f)], check=True, capture_output=True)
    return sig.read_bytes()


@proev("uden nøgle på maskinen er signering slået fra")
def _():
    # Bevidst valg: en maskine i drift må ikke kunne låse sig selv ude fra
    # opdateringer, fordi en nøgle mangler.
    b = bot({})
    lv.NOEGLE_STI = ARBEJDE / "findes-ikke.pub"
    assert b._tjek_signatur("print('hej')", None) is None


@proev("med nøgle: rigtig signatur godkendes, ændret kode afvises")
def _():
    hem, pub = _noegler()
    b = bot({})
    gammel = lv.NOEGLE_STI
    lv.NOEGLE_STI = pub
    try:
        kode = 'VERSION = "9.9"\nprint("hej")\n'
        sig = _signer(hem, kode)
        assert b._tjek_signatur(kode, sig) is None, "gyldig signatur blev afvist"

        # ÉT tegn ændret — det er hele pointen
        svar = b._tjek_signatur(kode + "# ondsindet linje\n", sig)
        assert svar and "passer ikke" in svar, f"ændret kode blev godkendt: {svar}"

        # ingen signatur, men nøgle til stede -> afvises
        svar = b._tjek_signatur(kode, None)
        assert svar and "ingen signatur" in svar, svar

        # signatur fra en FREMMED nøgle -> afvises
        fremmed_hem = ARBEJDE / "fremmed.key"
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA",
                        "-pkeyopt", "rsa_keygen_bits:2048",
                        "-out", str(fremmed_hem)],
                       check=True, capture_output=True)
        svar = b._tjek_signatur(kode, _signer(fremmed_hem, kode))
        assert svar and "passer ikke" in svar, \
            f"en fremmed nøgle blev godkendt: {svar}"
    finally:
        lv.NOEGLE_STI = gammel


@proev("prøvekørslen bruger appens EGEN python, ikke systemets")
def _():
    # Appen kører i et virtuelt miljø. Kaldte /opdater "python3", ville
    # prøvekørslen fejle på hver eneste ny version — og enhver opdatering
    # ville se defekt ud.
    # Der læses i selve kaldet, ikke i kommentarerne omkring det — ellers
    # ville prøven fejle på sin egen forklaring. (Det gjorde den først.)
    import ast
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    kald = []
    for node in ast.walk(ast.parse(kilde)):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "run"):
            continue
        if not node.args or not isinstance(node.args[0], ast.List):
            continue
        dele = [d.value if isinstance(d, ast.Constant) else ast.unparse(d)
                for d in node.args[0].elts]
        if dele and dele[0] == "xvfb-run":
            kald.append(dele)
    assert kald, "fandt ikke prøvekørslen i koden"
    for dele in kald:
        assert "sys.executable" in dele, \
            f"prøvekørslen bruger ikke sys.executable: {dele}"
        assert "python3" not in dele, \
            f"prøvekørslen kalder systemets python3: {dele}"


print("\nAdvarsler til administrator")


@proev("maskinen siger til, når nogen er tilføjet ud over de fem F-taster")
def _():
    seks = {str(10 + i): f"Person {i}" for i in range(6)}
    b = bot(seks, mode="enkelte")
    besk = b._tastadvarsel()
    assert "F-taster" in besk and "6 personer" in besk, besk
    # fem er stadig i orden
    fem = {str(10 + i): f"Person {i}" for i in range(5)}
    assert bot(fem, mode="enkelte")._tastadvarsel() == ""
    # og i fællestråd betyder tasterne ingenting
    assert bot(seks, mode="faellestraad")._tastadvarsel() == ""
    WHITELIST.write_text("{}")


# ---------------------------------------------------------- opsætningsmatrix
# Der findes FIRE opsætninger, ikke tre: mode (fællestråd | enkelte) gange
# betjening (knapper | tastatur). Prøverne ovenfor kører næsten alle sammen
# den samme kombination — skrivefelt i fællestråd — og derfor kunne en
# ændring i skrivefeltet gå ud over knap-tilstanden, uden at nogen prøve
# sagde fra. Her køres de samme kernescenarier gennem alle fire, så det, der
# ellers ville kræve fire maskiner stående, tager tre sekunder.
print("\nOpsætningsmatrix — alle fire kombinationer")

KOMBINATIONER = [(m, b) for m in ("faellestraad", "enkelte")
                 for b in ("knapper", "tastatur")]


def opsaetning(mode, betjening, **ekstra):
    """Bygger brugerfladen fra en RIGTIG config-fil, ikke fra dataclass-
    erstatning. Det er vigtigt: 'betjening' er ikke et felt på Config — den
    udleder både text_input, svar og taster i load(). Bygger man med
    dataclasses.replace, prøver man en kombination, der ikke kan opstå på en
    maskine."""
    d = json.loads(CONFIG.read_text())
    d.update(mode=mode, betjening=betjening, **ekstra)
    sti = ARBEJDE / f"config-{mode}-{betjening}.json"
    sti.write_text(json.dumps(d, ensure_ascii=False))
    c = lv.Config.load(sti)
    ui = lv.LivlineUI(c)
    ui.root.geometry(f"{ui.root.winfo_screenwidth()}x"
                     f"{ui.root.winfo_screenheight()}+0+0")
    ui.whitelist = lv.Whitelist(WHITELIST)
    ui.bot.whitelist = ui.whitelist
    ui.root.update()
    return ui


def med_folk(mode, betjening, **ekstra):
    WHITELIST.write_text(json.dumps({"11": "Mor", "22": "Jens"}))
    ui = opsaetning(mode, betjening, blink=False, **ekstra)
    sendte = []
    ui.bot.send_text = lambda ids, tekst, svar=None: sendte.append((tuple(ids), tekst))
    return ui, sendte


for _m, _b in KOMBINATIONER:

    @proev(f"betjeningsformen er entydig — {_m}/{_b}")
    def _(m=_m, b=_b):
        # Knapper og skrivefelt må aldrig være fremme samtidig: står der
        # både faste svar på tasterne og et felt at skrive i, kan de samme
        # tastetryk betyde to ting.
        ui, _ = med_folk(m, b)
        try:
            if b == "tastatur":
                assert ui.entry is not None, "intet skrivefelt i tastatur-tilstand"
                assert ui.config.replies == [], \
                    f"faste svar findes ved siden af skrivefeltet: {ui.config.replies}"
            else:
                assert ui.entry is None, "skrivefelt bygget i knap-tilstand"
                assert ui.config.replies, "ingen faste svar i knap-tilstand"
                assert len(ui.config.keys) == len(ui.config.replies), \
                    "der er ikke én tast pr. svar"
            # sidelisten hører til enkelte-tilstand og kun dér
            assert (ui.sidebar is None) == (m == "faellestraad"), \
                f"sideliste forkert i {m}"
        finally:
            luk(ui)

    @proev(f"besked ind, svar ud — og svaret bliver stående — {_m}/{_b}")
    def _(m=_m, b=_b):
        ui, sendte = med_folk(m, b)
        try:
            besked(ui, 11, "Mor", "hej fra mor")
            assert "hej fra mor" in paa_skaermen(ui), "beskeden kom ikke frem"
            ui._send_reply("mit svar")
            ui.root.update()
            assert "mit svar" in paa_skaermen(ui), "svaret ses ikke"
            assert any("mit svar" in x[1] for x in sendte), \
                f"svaret blev vist, men ikke sendt: {sendte}"
            # gentegning må ikke fjerne det igen (fejlen bag "den viser ikke
            # altid, at jeg har sendt noget")
            ui._tegn_samtale()
            ui.root.update()
            assert "mit svar" in paa_skaermen(ui), "svaret forsvandt ved gentegning"
        finally:
            luk(ui)

    @proev(f"automatikken rører intet og sender intet — {_m}/{_b}")
    def _(m=_m, b=_b):
        # Samme skrappe prøve som ovenfor, men kørt i alle fire opsætninger.
        # Det er her, en ændring i den ene tilstand typisk vil vise sig i
        # den anden.
        ui, sendte = med_folk(m, b)
        try:
            besked(ui, 11, "Mor", "ubesvaret besked")
            besked(ui, 22, "Jens", "og en mere")
            if ui.entry is not None:
                ui.entry.insert("1.0", "min halve sætning")
            ui._last_key = time.monotonic()      # lige rørt tastaturet
            ui.root.update()
            sendte.clear()
            foer = (ui.selected, set(ui._venter), set(ui._ukvitteret),
                    ui._kladde(), str(ui.root.focus_get()))

            ui._idle_check()
            ui._autosend_check()
            ui._vindue_vagt(3)
            ui._flash(2)
            ui._refresh_topbar()
            ui._poll_inbox()
            ui.root.update()

            efter = (ui.selected, set(ui._venter), set(ui._ukvitteret),
                     ui._kladde(), str(ui.root.focus_get()))
            assert foer == efter, \
                f"automatikken ændrede tilstanden:\n  før:  {foer}\n  efter: {efter}"
            assert sendte == [], f"automatikken sendte noget: {sendte}"
        finally:
            luk(ui)

    @proev(f"intet ryger uden for skærmen — {_m}/{_b}")
    def _(m=_m, b=_b):
        # Skrifter og knapper fylder forskelligt i de to betjeningsformer.
        # Prøven køres ved den største skrift, en bruger realistisk får.
        ui, _ = med_folk(m, b, skrift=44)
        try:
            besked(ui, 11, "Mor", "en ganske almindelig besked med lidt længde")
            sb, sh = ui.root.winfo_screenwidth(), ui.root.winfo_screenheight()
            assert ui.text.winfo_height() > sh * 0.35, \
                f"beskedfeltet blev klemt: {ui.text.winfo_height()} px af {sh}"
            for w in (ui.topbar, ui.text):
                assert w.winfo_rootx() + w.winfo_width() <= sb + 2, \
                    f"{w} rager ud til siden"
                assert w.winfo_rooty() + w.winfo_height() <= sh + 2, \
                    f"{w} rager ud i bunden"
            if ui.entry is not None:
                assert ui.entry.winfo_rootx() + ui.entry.winfo_width() <= sb + 2, \
                    "skrivefeltet rager ud til siden"
        finally:
            luk(ui)

    @proev(f"vinduesvagten holder vinduet øverst — {_m}/{_b}")
    def _(m=_m, b=_b):
        ui, _ = med_folk(m, b)
        try:
            kaldt = []
            rigtig = ui.root.attributes

            def spion(*a):
                kaldt.append(a)
                return rigtig(*a)
            ui.root.attributes = spion
            for n in (0, 1, 50):
                ui._vindue_vagt(n)
            ui.root.update()
            ui.root.attributes = rigtig
            topmost = [a for a in kaldt if a and a[0] == "-topmost" and a[1:] == (True,)]
            assert len(topmost) == 3, f"vinduet blev ikke sat øverst hver gang: {kaldt}"
        finally:
            luk(ui)

WHITELIST.write_text("{}")


@proev("versionen står i filens første linjer og stemmer med konstanten")
def _():
    # Filens hoved sagde "Version 4.35", mens VERSION var "4.51" — seksten
    # versioner bagud. Hovedet er det, et menneske læser først, så det er
    # dét, der bliver troet. Konstanten lå på linje 698 under 571 linjers
    # ændringslog, hvor ingen kiggede.
    import re
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    hoved = kilde.split("\n")[:12]
    m = [re.match(r"VERSION ([\d.]+)$", l) for l in hoved]
    m = [x for x in m if x]
    assert m, f"ingen VERSION-linje i filens første 12 linjer: {hoved}"
    assert m[0].group(1) == lv.VERSION, (
        f"hovedet siger v{m[0].group(1)}, men VERSION = {lv.VERSION}")
    nr = next(i for i, l in enumerate(kilde.split("\n"), 1)
              if l.startswith('VERSION = "'))
    assert nr < 200, f"VERSION-konstanten ligger på linje {nr} — for langt nede"


@proev("install.sh har sit eget versionsnummer, og det følger appen")
def _():
    import re
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    m = re.search(r'^INSTALL_VER="([^"]+)"', t, re.M)
    assert m, "install.sh har intet INSTALL_VER — man kan ikke se, hvilket script man har"
    assert m.group(1) == lv.VERSION, (
        f"install.sh er v{m.group(1)}, men appen er v{lv.VERSION}")
    # Og scriptet skal selv afvise et par, der ikke passer sammen.
    assert '"$INSTALL_VER" != "$APP_VER"' in t, \
        "install.sh sammenligner ikke sin egen version med appens"
    assert '"$DOC_VER" != "$APP_VER"' in t, \
        "install.sh tjekker ikke, at filens hoved og konstant er enige"


@proev('"nat" i config sætter nattetimerne — og en fejl siges højt')
def _():
    # Ét felt, ikke to: de to tal betyder kun noget i forhold til hinanden.
    c = dataclasses.replace(lv.Config.load(), nat=(23, 7))
    ui = lv.LivlineUI(c)
    try:
        from datetime import datetime as dt
        assert not ui._er_nat(dt(2026, 1, 1, 22, 30)), "22.30 er dag ved nat=[23,7]"
        assert ui._er_nat(dt(2026, 1, 1, 23, 30)), "23.30 skal være nat"
        assert ui._er_nat(dt(2026, 1, 1, 6, 0)), "06.00 skal være nat"
        assert not ui._er_nat(dt(2026, 1, 1, 7, 30)), "07.30 er dag ved nat=[23,7]"
    finally:
        luk(ui)
    # Ugyldige værdier må ALDRIG falde stille tilbage.
    for daarlig in ([25, 7], [22, 22], ["ti", 7], [22], "nat"):
        assert lv._nattetider(daarlig) == (lv.NAT_START, lv.NAT_SLUT), \
            f"{daarlig!r} burde give standarden"
    assert lv._nattetider(None) == (lv.NAT_START, lv.NAT_SLUT)
    assert lv._nattetider([21, 9]) == (21, 9)
    # Feltet skal være kendt, ellers meldes det som stavefejl
    assert "nat" in lv.KENDTE_FELTER


@proev("en genstart midt på dagen sender IKKE en ☀️-besked")
def _():
    # FEJL FUNDET VED GENNEMGANGEN: _nat_nu blev sat FØR sammenligningen med
    # None, så prøven var altid sand. Hver eneste dagtidsgenstart — også
    # efter /opdater — sendte et livstegn. Med ti maskiner er det præcis den
    # støj, vi skar væk i 4.51.
    ui = byg()
    sendt = []
    ui.bot = types.SimpleNamespace(send_admin=sendt.append,
                                   _status_text=lambda: "status")
    try:
        ui._nat_nu = None                       # frisk start
        ui._er_nat = lambda naar=None: False    # det er dag
        ui._panel = lambda t: None
        ui._baglys = lambda v: None
        ui.root.after = lambda *a, **k: None    # ingen næste runde
        ui._nat_vagt()
        assert not sendt, f"første runde skal være tavs, men sendte: {sendt}"
        ui._nat_nu = True                       # nu HAR det været nat
        ui._nat_vagt()
        assert sendt and sendt[0].startswith("☀️"), \
            f"morgenens livstegn mangler: {sendt}"
    finally:
        luk(ui)


@proev("skærmen sættes hver runde — der måles ikke på den")
def _():
    # Samme regel som vinduesvagten. Den farlige fejl er en skærm, der
    # bliver sort om morgenen: så ligner maskinen en, der er død, og
    # familien ringer ikke — de tror bare, den er gået i stykker.
    ui = byg()
    kaldt = []
    ui.bot = types.SimpleNamespace(send_admin=lambda t: None,
                                   _status_text=lambda: "")
    try:
        ui._panel = lambda t: kaldt.append(t)
        ui._baglys = lambda v: None
        ui._er_nat = lambda naar=None: False
        ui.root.after = lambda *a, **k: None
        ui._nat_nu = False          # ingen ændring — den må IKKE springe over
        for _ in range(3):
            ui._nat_vagt()
        assert kaldt == [True, True, True], \
            f"skærmen skal sættes hver runde, blev kaldt: {kaldt}"
    finally:
        luk(ui)


@proev("om natten vækkes skærmen af et tastetryk og slukker igen bagefter")
def _():
    ui = byg()
    kaldt = []
    ui.bot = types.SimpleNamespace(send_admin=lambda t: None,
                                   _status_text=lambda: "")
    try:
        ui._panel = lambda t: kaldt.append(t)
        ui._baglys = lambda v: None
        ui._er_nat = lambda naar=None: True
        ui.root.after = lambda *a, **k: None
        ui._nat_nu = True
        ui._last_key = time.monotonic()          # nogen rørte lige en tast
        ui._nat_vagt()
        assert kaldt[-1] is True, "skærmen skal være tændt lige efter et tastetryk"
        ui._last_key = time.monotonic() - lv.NAT_VAEK_SEK - 1
        ui._nat_vagt()
        assert kaldt[-1] is False, "skærmen skal slukke igen efter ro"
    finally:
        luk(ui)


@proev("fællestråden viser HVAD der er sket og HVORNÅR — ikke en overskrift")
def _():
    # Hovedet stod før med "Fællestråd — alle ser dine svar" hele dagen:
    # sandt, men uden oplysning. Nu bærer det samme indhold som i den anden
    # tilstand — ny besked med klokkeslæt, og læst med klokkeslæt bagefter.
    # Navnet i hovedet slås op på whitelisten. Prøven satte den ikke, og
    # kaldte så en manglende opsætning for en fejl i programmet. I drift
    # kommer en besked kun igennem fra en, der står på listen.
    WHITELIST.write_text(json.dumps({"111": "Ulrik"}))
    ui = byg(mode="faellestraad", blink=False)
    ui.whitelist = lv.Whitelist(WHITELIST)
    try:
        besked(ui, 111, "Ulrik", "Hej mor")
        ui.root.update()
        hoved = ui._top_tekst.cget("text")
        assert "Ny besked" in hoved, f"hovedet siger ikke, at der er nyt: {hoved!r}"
        assert "ULRIK" in hoved.upper(), f"afsenderens navn mangler: {hoved!r}"
        assert ui._top_tegn.cget("text") == "■", "manglende rødt mærke ved ny besked"
        ui._kvitter(111)
        ui.root.update()
        hoved = ui._top_tekst.cget("text")
        assert "Læst" in hoved or "Du svarede" in hoved, \
            f"hovedet siger ikke, at beskeden er set: {hoved!r}"
        assert ui._top_tegn.cget("text") == "✓", "manglende grønt flueben efter kvittering"
    finally:
        WHITELIST.write_text("{}")
        luk(ui)


@proev("knapraden er slået FRA som standard — og kan tændes til touch")
def _():
    # Svarteksterne skrives fysisk over tasterne, så raden var en
    # gentagelse, der tog plads fra beskeder og billeder. Den skal kunne
    # tændes igen: på en touch-skærm er knapperne ikke en gentagelse, men
    # den eneste måde at svare på.
    grund = json.loads(CONFIG.read_text())
    sti = ARBEJDE / "standardknapper.json"
    sti.write_text(json.dumps({**grund, "betjening": "knapper"},
                              ensure_ascii=False))
    assert lv.Config.load(sti).show_buttons is False, \
        "knapraden skal være slået fra som standard"
    sti.write_text(json.dumps({**grund, "betjening": "knapper",
                               "vis_knapper": True}, ensure_ascii=False))
    assert lv.Config.load(sti).show_buttons is True, \
        "knapraden skal kunne tændes igen"
    # Slået fra: ingen knapper bygges, men tasterne virker uændret
    ui = byg(text_input=False, show_buttons=False,
             replies=["Tak", "Ring til mig"], keys=["Q", "O"])
    try:
        assert not ui._knapper, "der blev bygget knapper, selvom de er slået fra"
        assert ui.replies, "de faste svar skal stadig findes"
    finally:
        luk(ui)


@proev("svarknapperne viser kun teksten — tasten står på tastaturet")
def _():
    # Bogstavet er skrevet fysisk over tasten på maskinen. På skærmen var
    # "[Q]" en gentagelse, der tog plads fra selve ordene.
    ui = byg(text_input=False, show_buttons=True,
             replies=["Tak", "Ring til mig"], keys=["Q", "O"])
    try:
        for knap in ui._knapper:
            t = knap.cget("text")
            assert "[" not in t and "]" not in t, f"tasten står stadig på knappen: {t!r}"
        tekster = [k.cget("text") for k in ui._knapper]
        assert tekster == ["Tak", "Ring til mig"], tekster
    finally:
        luk(ui)


@proev("Enter kvitterer OGSÅ i knap-tilstand — samme betydning overalt")
def _():
    # Hullet i opsætningsmatricen: i knap-tilstand fandtes skrivefeltet ikke,
    # så Enter gjorde ingenting. Eneste vej til at kvittere var at SENDE et
    # svar — og dermed blev "jeg har set det" og "jeg svarer dig" til det
    # samme. For den, der sidder med telefonen, er de to ting forskellige.
    for tilstand in ("faellestraad", "enkelte"):
        ui = byg(mode=tilstand, text_input=False, show_buttons=True)
        try:
            assert ui.entry is None, "prøven giver kun mening uden skrivefelt"
            kvitteret = []
            ui._kvitter = lambda cid, svarer=False: kvitteret.append(cid)
            ui.last_sender = 111
            ui.root.event_generate("<KeyPress-Return>")
            ui.root.update()
            assert kvitteret, f"Enter kvitterede ikke i {tilstand}/knapper"
        finally:
            luk(ui)


@proev("hjælpelinjen siger GRUPPEN i fællestråd og NAVNET i enkelte")
def _():
    # Ordet skal passe med det, der faktisk sker. I fællestråd svarer man
    # dem alle sammen, uanset hvem der skrev sidst.
    ui = byg(mode="faellestraad", text_input=True)
    try:
        besked(ui, 111, "Ulrik", "Hej mor")
        ui.root.update()
        t = ui._hjaelp.cget("text")
        assert "gruppen" in t, f"fællestråd bør sige 'gruppen': {t!r}"
        assert "Skriv" in t and "Enter" in t, f"begge veje mangler: {t!r}"
    finally:
        luk(ui)
    ui = byg(mode="enkelte", text_input=True)
    try:
        besked(ui, 111, "Ulrik", "Hej mor")
        ui._select_fkey(0)
        ui.root.update()
        t = ui._hjaelp.cget("text")
        assert "gruppen" not in t, f"enkelte må ikke sige 'gruppen': {t!r}"
    finally:
        luk(ui)


@proev("hjælpelinjen findes og opdateres OGSÅ i knap-tilstand")
def _():
    # Knap-tilstand betyder faste svar. Uden "svar" og "taster" bygger
    # appen ingen knaprad — og så heller ingen hjælpelinje. Prøven satte
    # dem ikke og byggede dermed en maskine, Config.load aldrig kan lave:
    # knapper uden noget at trykke på. Det var prøven, der var forkert.
    ui = byg(mode="faellestraad", text_input=False, show_buttons=True,
             replies=list(lv.DEFAULT_REPLIES), keys=list(lv.DEFAULT_KEYS))
    try:
        assert getattr(ui, "_hjaelp", None) is not None, \
            "der er ingen hjælpelinje i knap-tilstand"
        # Intet ukvitteret: linjen skal tie
        ui._ukvitteret.clear()
        ui._refresh_topbar()
        ui.root.update()
        assert ui._hjaelp.cget("text") == "", \
            "linjen skal være tom, når der ikke er noget at kvittere for"
        # Noget venter: linjen skal fortælle, hvad Enter gør
        ui.last_sender = 111
        ui._ukvitteret.add(111)
        ui._refresh_topbar()
        ui.root.update()
        assert "Enter" in ui._hjaelp.cget("text"), \
            f"linjen siger ikke hvad Enter gør: {ui._hjaelp.cget('text')!r}"
    finally:
        luk(ui)


@proev("standardsvarene er de fem, der er prøvet af i drift")
def _():
    # De tre gamle standardsvar var gættet. Disse fem kom fra en maskine,
    # der havde stået i en stue — og de er dem, en ny maskine skal starte
    # med, så maskine 02 begynder, hvor 01 endte.
    assert lv.DEFAULT_REPLIES == ["Tak", "Nej tak", "Alt er godt",
                                  "Ikke så godt", "Ring til mig"]
    assert lv.DEFAULT_KEYS == ["Q", "X", "T", "N", "O"]
    assert len(lv.DEFAULT_KEYS) == len(lv.DEFAULT_REPLIES), \
        "hvert svar skal have en tast"
    assert len(set(lv.DEFAULT_KEYS)) == len(lv.DEFAULT_KEYS), \
        "to svar må ikke dele tast"
    # Uden "taster" i config skal standarden bruges — ikke 1,2,3
    grund = json.loads(CONFIG.read_text())
    sti = ARBEJDE / "standardtaster.json"
    sti.write_text(json.dumps({**grund, "betjening": "knapper"},
                              ensure_ascii=False))
    c = lv.Config.load(sti)
    assert c.keys == lv.DEFAULT_KEYS, f"fik {c.keys}"
    assert c.replies == lv.DEFAULT_REPLIES


@proev("gennemgangen af widgets kan ikke løbe i ring")
def _():
    # v4.52 skrev "w = w or self.root". Blev en widget vurderet som falsk,
    # startede gennemgangen forfra på roden — og 75 prøver faldt med
    # RecursionError. Prøven her fanger netop den slags: en widget, der
    # påstår, den er tom.
    ui = byg()
    try:
        class Falsk:
            """Opfører sig som en widget, men er 'falsk' i Pythons forstand."""
            def __len__(self):
                return 0
            def __str__(self):
                return "falsk-widget"
            def configure(self, **k):
                pass
            def winfo_children(self):
                return []
        ui._skjul_markoer(Falsk())      # må ikke løbe videre til roden
    finally:
        luk(ui)


@proev("musemarkøren er skjult på ALLE flader, ikke kun beskedfeltet")
def _():
    # cursor="none" stod kun på Text-widgetten. Overalt andet lå pilen
    # synlig — og om natten lyste den.
    ui = byg()
    try:
        ui._skjul_markoer()
        ui.root.update()
        synlige = []

        def gaa(w):
            try:
                if str(w.cget("cursor")) not in ("none",):
                    synlige.append(str(w))
            except tk.TclError:
                pass
            for barn in w.winfo_children():
                gaa(barn)
        gaa(ui.root)
        assert not synlige, f"markøren er stadig synlig på: {synlige[:5]}"
    finally:
        luk(ui)


@proev("svarknapperne bliver inden for skærmen — også med fem svar")
def _():
    # Set i drift: fem svar på en 1366 px skærm lå på én række uden at
    # bryde, så rækken blev bredere end skærmen. Fjerde gang samme rod.
    ui = byg(text_input=False, show_buttons=True,
             replies=["Tak", "Nej tak", "Alt er godt", "Ikke så godt",
                      "Ring til mig"],
             keys=["Q", "X", "T", "M", "O"])
    try:
        ui.root.update_idletasks()
        ui._juster_bredder()
        ui.root.update_idletasks()
        skaerm = ui.root.winfo_screenwidth()
        bred = ui.botbar.winfo_reqwidth()
        assert bred <= skaerm, \
            f"knaprækken vil fylde {bred} px på en {skaerm} px skærm"
        for knap in ui._knapper:
            w = int(knap.cget("wraplength"))
            assert w > 0, "knappen bryder ikke sin tekst"
            assert knap.winfo_reqwidth() <= skaerm // 2, \
                f"én knap beder om {knap.winfo_reqwidth()} px"
    finally:
        luk(ui)


@proev("kvitteringen bliver en boble på skærmen — og bliver stående")
def _():
    # Før skete der to ting ved Enter: familien fik 👁, og hovedet ØVERST
    # skiftede. Men brugeren kigger på tastaturet, ikke opad — så for hende
    # så det ud, som om der ikke skete noget, og så trykker man igen.
    WHITELIST.write_text(json.dumps({"111": "Ulrik"}))
    ui = byg(mode="faellestraad", blink=False)
    ui.whitelist = lv.Whitelist(WHITELIST)
    try:
        sendt = []
        ui.bot = types.SimpleNamespace(
            send_text=lambda ids, t: sendt.append((ids, t)),
            send_admin=lambda t: None, _status_text=lambda: "")
        besked(ui, 111, "Ulrik", "Hej far")
        ui.root.update()
        foer = len(ui._rows)
        ui._kvitter(111)
        ui.root.update()
        assert len(ui._rows) == foer + 1, "kvitteringen blev ikke lagt i samtalen"
        r = ui._rows[-1]
        assert r["egen"] is True, "kvitteringen skal stå som brugerens egen"
        assert r["tekst"].startswith(lv.KVIT_MAERKE), r["tekst"]
        assert sendt, "afsenderen fik ingen besked om, at den var set"
        # Den skal overleve, at samtalen tegnes forfra
        ui._tegn_samtale()
        ui.root.update()
        assert any(str(r.get("tekst", "")).startswith(lv.KVIT_MAERKE)
                   for r in ui._rows), "kvitteringen forsvandt ved gentegning"
    finally:
        WHITELIST.write_text("{}")
        luk(ui)


@proev("Enter virker, selv om afsenderen er fjernet fra whitelisten")
def _():
    # Skrækscenariet: en besked står ulæst, administrator fjerner personen
    # fra whitelisten, og nu kan brugeren IKKE kvittere. Intet sker ved
    # Enter, det røde mærke bliver stående, og hun trykker igen og igen.
    # En låst skærm er det værste, maskinen kan gøre — der er ingen til at
    # trykke hende fri.
    WHITELIST.write_text(json.dumps({"111": "Ulrik"}))
    ui = byg(mode="faellestraad", blink=False)
    ui.whitelist = lv.Whitelist(WHITELIST)
    try:
        sendt = []
        ui.bot = types.SimpleNamespace(
            send_text=lambda ids, t: sendt.append((ids, t)),
            send_admin=lambda t: None, _status_text=lambda: "")
        besked(ui, 111, "Ulrik", "Hej far")
        ui.root.update()
        # … og nu ryger han af listen, mens beskeden stadig venter
        WHITELIST.write_text("{}")
        ui.whitelist = lv.Whitelist(WHITELIST)
        foer = len(ui._rows)
        ui._kvitter(111)
        ui.root.update()
        assert 111 not in ui._ukvitteret, \
            "skærmen sidder fast: beskeden kan ikke kvitteres væk"
        assert len(ui._rows) == foer + 1, \
            "brugeren fik ingen boble — Enter så ud til ikke at virke"
        assert sendt == [], \
            f"der blev skrevet til en, der er taget af listen: {sendt}"
    finally:
        WHITELIST.write_text("{}")
        luk(ui)


@proev("i fællestråd får ALLE I TRÅDEN at vide, at beskeden er læst")
def _():
    # Løftet i fællestråd er, at alle ser alt. Derfor går kvitteringen til
    # hele tråden — ikke kun til dem, der lige har skrevet. Datteren vil
    # gerne vide, at far har læst med, også når det var svigersønnen, der
    # skrev. Prøvet af i drift: med kun de ventende som modtagere lignede
    # maskinen en, der kun svarede den, der råbte højest.
    WHITELIST.write_text(json.dumps({"111": "Ulrik", "222": "Mette"}))
    ui = byg(mode="faellestraad", blink=False)
    ui.whitelist = lv.Whitelist(WHITELIST)
    try:
        sendt = []
        ui.bot = types.SimpleNamespace(
            send_text=lambda ids, t: sendt.append((list(ids), t)),
            send_admin=lambda t: None, _status_text=lambda: "")
        # KUN den ene skriver — den anden skal ALLIGEVEL have besked
        besked(ui, 111, "Ulrik", "Hej far")
        ui.root.update()
        ui._kvitter(ui.last_sender)
        ui.root.update()
        assert sendt, "ingen fik besked om, at det var læst"
        assert set(sendt[0][0]) == {111, 222}, \
            f"kun nogle i tråden fik kvitteringen: {sendt[0][0]}"
        assert "Jeres" in sendt[0][1], \
            f"fællestråd skal sige 'jeres', ikke 'din': {sendt[0][1]!r}"
        assert not ui._ukvitteret, f"nogen står stadig som ventende: {ui._ukvitteret}"
        # Én handling, én boble — ikke én pr. person
        kvit = [r for r in ui._rows
                if str(r.get("tekst", "")).startswith(lv.KVIT_MAERKE)]
        assert len(kvit) == 1, f"der kom {len(kvit)} kvitteringsbobler"
    finally:
        luk(ui)
        WHITELIST.write_text(json.dumps({"111": "Ulrik"}))


@proev("et svar giver IKKE en kvitteringsboble oveni")
def _():
    # Svaret er selv kvitteringen. To bobler for én handling ville fylde
    # samtalen med noget, der ikke er sagt.
    ui = byg(mode="faellestraad", blink=False)
    try:
        ui.bot = types.SimpleNamespace(
            send_text=lambda ids, t: None,
            send_admin=lambda t: None, _status_text=lambda: "")
        besked(ui, 111, "Ulrik", "Hej far")
        ui.root.update()
        foer = len(ui._rows)
        ui._kvitter(111, svarer=True)
        ui.root.update()
        assert len(ui._rows) == foer, "der kom en kvitteringsboble ved et svar"
    finally:
        luk(ui)


@proev("efter en kvittering står der LÆST, ikke 'Du svarede'")
def _():
    # En kvittering er ikke et svar, og statuslinjen skal sige det rigtige.
    ui = byg(mode="enkelte", blink=False)
    try:
        ui.bot = types.SimpleNamespace(
            send_text=lambda ids, t: None,
            send_admin=lambda t: None, _status_text=lambda: "")
        besked(ui, 111, "Ulrik", "Hej far")
        ui.root.update()
        ui._kvitter(111)
        ui.root.update()
        status, _ = ui._samtalestatus(111)
        assert status.startswith("Læst"), f"fik {status!r}"
        # Et rigtigt svar skal stadig sige "Du svarede"
        ui._rows.append({"navn": "Du", "chat_id": 111, "type": "text",
                         "tekst": "Tak", "fil": None,
                         "tid": lv.datetime.now().isoformat(),
                         "egen": True})
        status, _ = ui._samtalestatus(111)
        assert status.startswith("Du svarede"), f"fik {status!r}"
    finally:
        luk(ui)


@proev("install.sh giver kiosk-brugeren adgang til baggrundslyset")
def _():
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    assert "90-livline-baglys.rules" in t, "udev-reglen mangler"
    assert 'usermod -aG video' in t, "kiosk-brugeren kommer ikke i gruppen video"
    # Her stod før: assert 'test -w "$d/brightness"' in t
    #
    # Prøven låste sig fast på HVORDAN der blev kontrolleret i stedet for
    # AT der blev kontrolleret — og gik derfor i stykker, da kontrollen
    # blev gjort bedre (test -w gav falsk alarm, se v4.66). En prøve skal
    # beskrive kravet, ikke opskriften. Kravet er: der skal ske en rigtig
    # kontrol af, at kiosk-brugeren kan skrive.
    assert "KONTROLLÉR DET" in t, \
        "install.sh kontrollerer ikke, at adgangen FAKTISK virker"


@proev("en autologin, der peger forkert, stopper installationen")
def _():
    # Pegede GDM på en anden bruger, skrev scriptet en ADVARSEL og fortsatte
    # til "Færdig" — hvor der står, at maskinen logger selv ind og starter
    # Livline. Efter genstarten stod skærmen tom, og det kan IKKE rettes
    # over Tailscale: uden grafisk session ingen app, og uden app intet
    # livstegn. Så skal der køres ud til maskinen.
    #
    # En tilstand, der garanteret forhindrer opstart, må ikke være en
    # advarsel, man kan overse klokken elleve om aftenen.
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    kode = "\n".join(l for l in t.splitlines()
                     if not l.lstrip().startswith("#"))
    blok = kode.split("Aktiverer automatisk login")[1].split("echo \"--")[0]
    assert "exit 1" in blok, \
        "en forkert autologin er stadig kun en advarsel — skærmen står tom"
    assert "cp -a /etc/gdm3/custom.conf" in blok, \
        "der tages ingen kopi, før GDM's opsætning ændres"
    assert "AutomaticLogin=$KIOSK_USER" in blok, \
        "autologin rettes ikke til kiosk-brugeren"


@proev("lysstyrken kan sættes pr. maskine — og fuld styrke er ikke standard-svaret")
def _():
    # MÅLT PÅ HARDWARE (maskine 02, T470s, 28.09): 50 % af maksimum var
    # tydeligt lettere at læse på tre meters afstand end 100 %. Fuldt
    # baglys vasker det sorte ud, så teksten træder mindre frem — og det
    # er kontrasten, aldersøjne læser efter, ikke lysmængden.
    #
    # To genbrugsskærme er sjældent ens, så det skal kunne sættes pr.
    # maskine. Men standarden bliver 100, så maskiner i drift ikke ændrer
    # sig af sig selv ved en opdatering.
    assert lv.Config.load().lysstyrke == 100, \
        "standarden er ikke længere 100 — maskiner i drift ville ændre sig"

    # Tallet skal faktisk bruges, når baglyset sættes
    kilde = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    blok = kilde.split("def _baglys")[1].split("def ")[0]
    assert "self.config.lysstyrke" in blok, \
        "lysstyrken læses fra config, men bruges ikke, når lyset sættes"
    assert "max(1," in blok, \
        "en lav procent kan slukke skærmen helt om dagen — " \
        "en maskine, der ser død ud, og som han ikke kan trykke sig ud af"

    # En forkert værdi må ALDRIG falde stille tilbage
    for daarlig in (0, -5, 200, "halvt", [50], None):
        v = lv._lysstyrke(daarlig)
        assert v == 100, f"{daarlig!r} gav {v}, ikke 100"
    for god in (1, 50, 70, 100):
        assert lv._lysstyrke(god) == god
    assert "Ugyldig \"lysstyrke\"" in kilde, \
        "en forkert lysstyrke siges ikke højt i loggen"

    # Og /indstillinger skal vise det, maskinen FAKTISK bruger
    assert "Lysstyrke:" in kilde, \
        "/indstillinger viser ikke lysstyrken — så kan den ikke tjekkes udefra"


@proev("ingen anden end Livline må røre lysstyrken")
def _():
    # Set på maskine 02 (28.09): skærmen skiftede lysstyrke af sig selv, og
    # et tastetryk bragte den op igen. Det lignede en dårlig skærm.
    #
    # To systemer sloges om den samme fil: GNOME dæmper efter inaktivitet
    # og skruer op ved næste tast, mens Livlines nattevagt skriver
    # max_brightness hvert halve minut. En skærm, der skifter af sig selv,
    # ser i en dement mands stue ud, som om maskinen er ved at gå i stykker
    # — og han kan ikke spørge nogen om det.
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    kode = "\n".join(l for l in t.splitlines()
                     if not l.lstrip().startswith("#"))
    for indstilling in ("idle-dim false",
                        "ambient-enabled false",
                        "night-light-enabled false"):
        assert indstilling in kode, \
            f"{indstilling!r} sættes ikke — skærmen kan stadig ændre sig selv"

    # Og appen skal stadig selv styre baglyset, ellers har vi kun slukket
    # for den ene af de to.
    app = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    assert "def _baglys" in app, "appen styrer ikke længere baglyset"


@proev("install.sh slår genvejstasterne fra")
def _():
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    for n in ("overlay-key", "toggle-overview", "switch-applications",
              "panel-run-dialog", "media-keys terminal"):
        assert n in t, f"genvejen {n} slås ikke fra"
    assert "lock-enabled false" in t, \
        "låseskærmen skal være fra, ellers kan der komme et kodebillede foran appen"


@proev("appens udskrift havner i journalen — ellers er maskinen blind")
def _():
    # Maskinen kørte i månedsvis uden at føre log over sig selv. run.sh
    # startede appen uden omdirigering, så hver "Kunne ikke sende til …"
    # faldt på gulvet. Opdaget, da en kvittering kun nåede den ene af to
    # telefoner, og der ikke var noget at læse.
    #
    # Det er værre end en manglende funktion: en maskine, der står i en
    # fremmed stue, kan kun fejlfindes gennem det, den har skrevet ned.
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    assert "systemd-cat -t livline" in t, \
        "appen startes uden at dens udskrift fanges — fejl bliver usynlige"
    assert "PYTHONUNBUFFERED" in t, \
        "uden den kommer linjerne først, når appen dør"
    # /status aflæser journalen under netop dette navn. Bruger run.sh et
    # andet, ser maskinen sund ud, selv om Telegram har været væk i timer.
    assert 'journalctl", "-b", "-t", "livline"' in t or "-t livline" in t, \
        "/status og run.sh skal bruge samme navn i journalen"


@proev("install.sh PRØVER at skrive til baglyset i stedet for at spørge")
def _():
    # Kontrollen brugte "test -w", som spurgte om lov og fik nej — mens en
    # rigtig skrivning som samme bruger lykkedes. Resultatet var en advarsel
    # på hver eneste installation. En advarsel, der råber uden grund, lærer
    # én at overse advarsler, og så står den ægte fejl i en log, ingen læser.
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    baglys = t.split("KONTROLLÉR DET")[1].split("livline-vis")[0]
    # Kun KODEN tæller. Første udgave af denne prøve faldt over sin egen
    # forklaring: kommentaren fortæller, hvorfor "test -w" blev fjernet,
    # og prøven læste det som om den stadig blev brugt.
    kode = "\n".join(l for l in baglys.splitlines()
                     if not l.lstrip().startswith("#"))
    assert "test -w" not in kode, \
        "kontrollen spørger om lov i stedet for at prøve at skrive"
    assert ">" in kode and "sudo -u" in kode, \
        "der foretages ingen rigtig skrivning som kiosk-brugeren"
    assert "bl_power" in baglys, \
        "kun lysstyrken prøves — bl_power er den, der slukker panellyset"
    # bl_power skal også have rettigheder med det samme, ikke først ved
    # næste opstart: det er den fil, der gør skærmen helt mørk kl. 22
    rettigheder = t.split("Sæt rettighederne med det samme")[1].split("KONTROLLÉR")[0]
    assert "bl_power" in rettigheder, \
        "bl_power får først rettigheder ved næste genstart"


@proev("install.sh tåler, at et pakkespejl hikker")
def _():
    # Set i drift: dk.archive.ubuntu.com var midt i en synkronisering,
    # apt-get update fejlede, og set -e afbrød hele installationen — på en
    # maskine, hvor hver eneste pakke i forvejen var installeret.
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    assert "apt-get update -q ||" in t, \
        "et spejl, der hikker, kan stoppe hele installationen"


@proev("install.sh lukker for alt andet, der kan åbne et vindue")
def _():
    # Set i drift på maskine 04: et notifikationsvindue lagde sig oven på
    # Livline, og skærmen viste Ubuntus skrivebord. Appen kørte upåklageligt
    # imens — loggen var ren, og maskinen troede selv, at alt var godt.
    #
    # Vinduesvagten kan IKKE tage forgrunden tilbage på Wayland. Derfor er
    # den eneste sikring, at de andre vinduer aldrig bliver til noget.
    #
    # Den, der fandt fejlen, lukkede vinduet med musen. Det kan brugeren ikke.
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    assert "Hidden=true" in t, \
        "autostart-programmerne slås ikke fra — et vindue kan lægge sig foran"
    for navn in ("update-notifier", "ubuntu-advantage-notification",
                 "orca-autostart", "org.gnome.Evolution-alarm-notify"):
        assert navn in t, f"{navn} kan stadig åbne et vindue oven på Livline"
    assert "snap remove --purge firmware-updater" in t, \
        "firmware-snappen melder opdateringer på skærmen i stuen"
    # im-launch må ALDRIG slås fra: uden den kan tastaturet svigte, og så
    # er der ingen vej ind i maskinen for den, der sidder foran den.
    assert "im-launch" not in t.split("for d in")[1].split("done")[0], \
        "im-launch står på listen over programmer, der slås fra"


@proev("livline-wifi findes — og koden havner aldrig i historikken")
def _():
    # En WiFi-kode på kommandolinjen havner i ~/.bash_history og i
    # maskinens proces-liste, og bliver liggende i årevis på en maskine i
    # en fremmed stue. Det var nær sket én gang.
    #
    # Nettet skal desuden kunne lægges ind, MENS maskinen står hjemme hos
    # den, der bygger den. Ellers skal koden tastes i familiens stue —
    # og så laver man teknik foran dem, hvilket leveringsnoten forbyder.
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    assert "/usr/local/bin/livline-wifi" in t, \
        "livline-wifi lægges ikke på maskinen"
    blok = t.split("livline-wifi: læg et netværk ind")[1].split("WIFIEOF")[1]
    assert "read -rsp" in blok, \
        "koden tastes ikke skjult — den kan ende i historikken"
    assert "connection add type wifi" in blok, \
        "et net uden for rækkevidde kan ikke lægges ind hjemmefra"

    # MÅ ALDRIG KOBLE PÅ MED DET SAMME.
    # Maskinen fjernstyres over det net, den står på. Begynder den at
    # skifte, ryger SSH-forbindelsen i samme sekund — før man når at taste
    # koden. Set to gange i drift, og anden gang ventede den 90 sekunder
    # på en kode, ingen kunne skrive.
    # Kun KODEN tæller. Kommentaren forklarer netop, hvorfor "device wifi
    # connect" blev fjernet — og første udgave af prøven læste sin egen
    # forklaring som om linjen stadig blev brugt. Anden gang samme fælde.
    kode = "\n".join(l for l in blok.splitlines()
                     if not l.lstrip().startswith("#"))
    assert "device wifi connect" not in kode, \
        "kommandoen kobler på med det samme og river fjernforbindelsen væk"

    # Koden kan ikke ses, mens den tastes. Så skal den tastes to gange —
    # ellers opdages tastefejlen først hos familien, hvor maskinen bare
    # ikke vil koble sig på, og ingen kan se hvorfor.
    assert blok.count("read -rsp") >= 2, \
        "koden tastes kun én gang — en tastefejl opdages først hos familien"
    assert "mindst 8 tegn" in blok, \
        "for kort kode giver nmcli's uforståelige 'psk: property is invalid'"


@proev("/opdater kan ikke tændes uden en nøgle at kontrollere med")
def _():
    # FAIL-OPEN VAR DEN FORKERTE VEJ. Appen kontrollerer kun underskriften,
    # hvis /etc/livline/opdater.pub findes — og installationen lagde den
    # aldrig på. En ny maskine med en update-URL tog derfor imod hvad som
    # helst fra den adresse og kørte det. En overtaget GitHub-konto eller
    # en ændret adresse var nok til at få fremmed kode ind i en stue.
    #
    # Syntakstjek og prøvekørsel viser, at kode KAN køre. De siger intet
    # om, hvem der har sendt den.
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    kode = "\n".join(l for l in t.splitlines()
                     if not l.lstrip().startswith("#"))

    assert "NOEGLEFIL" in kode, "installationen spørger ikke om den offentlige nøgle"
    blok = kode.split('if [[ -n "$UPDATE_URL" ]]; then')[1].split("\nfi\n")[0]
    # Uden nøgle SKAL update-URL'en tømmes. Ellers står maskinen med
    # /opdater tændt og ingen kontrol.
    assert blok.count('UPDATE_URL=""') >= 3, \
        "/opdater bliver stående tændt, selv om der ingen nøgle er"
    assert "openssl pkey -pubin" in blok, \
        "nøglen kontrolleres ikke — en forkert fil ville afvise ALT senere"
    assert "install -o root -g root -m 644" in kode and "opdater.pub" in kode, \
        "nøglen lægges ikke root-ejet på maskinen"

    # Appens side af aftalen: uden nøgle er signering slået fra — det er
    # med vilje (en maskine i drift må ikke kunne låse sig selv ude), og
    # derfor er det installationens ansvar, at nøglen ER der.
    app = pathlib.Path(lv.__file__).read_text(encoding="utf-8")
    assert "if not NOEGLE_STI.exists():" in app, \
        "appen har ændret adfærd — gennemgå aftalen mellem app og installation"


@proev("root kører intet fra en mappe, kiosk-brugeren kan skrive i")
def _():
    # EN VEJ FRA APPEN TIL ROOT. /opt/livline ejes af kiosk-brugeren — det
    # skal den, for /opdater udskifter livline_bot.py. Men de to scripts,
    # ROOT kører fra cron (netcheck hvert kvarter, hardware hver nat), lå i
    # samme mappe. Filerne var root-ejede, mappen var ikke — og den, der må
    # skrive i en mappe, må også omdøbe og erstatte filerne i den.
    #
    # Kunne nogen køre kode som Livline-brugeren — et billede, der vælter
    # Pillow, eller en Python-pakke, der bliver overtaget — kunne de lægge
    # deres egen netcheck.sh og have root et kvarter senere.
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    kode = "\n".join(l for l in t.splitlines()
                     if not l.lstrip().startswith("#"))

    # Hver cron-linje, der kører som root, skal pege uden for /opt/livline
    for linje in kode.splitlines():
        if "cron.d" not in linje or "echo" not in linje:
            continue
        assert "/opt/livline" not in linje, \
            f"root kører noget fra kiosk-brugerens mappe: {linje.strip()}"

    assert "install -d -o root -g root -m 755 /usr/local/libexec/livline" in kode, \
        "der oprettes ingen root-ejet mappe til de scripts, root kører"
    for navn in ("netcheck.sh", "hardware.py"):
        assert f"/usr/local/libexec/livline/{navn}" in kode, \
            f"{navn} ligger ikke i den root-ejede mappe"
        assert f"rm -f /opt/livline/netcheck.sh" in kode, \
            "gamle kopier i /opt/livline ryddes ikke væk ved genkørsel"

    # Og installationen skal KONTROLLERE det til sidst. Den slags bliver
    # stille lavet om senere — af en genkørsel, en oprydning, en god idé.
    assert "root-opgaverne ligger uden for kiosk-brugerens rækkevidde" in kode, \
        "der kontrolleres ikke til sidst, at ejerskabet faktisk blev sat"


@proev("nødnettet lægges ind ved installationen — og kan springes over")
def _():
    # Alt, der skal gøres "bagefter", bliver glemt på maskine 07. Nødnettet
    # er det net, maskinen kan finde, når familiens eget er væk, og du står
    # i stuen med telefonen som hotspot. Uden det skal der kabel eller
    # tastatur til — og tastaturet ligger under et stykke papir.
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    kode = "\n".join(l for l in t.splitlines()
                     if not l.lstrip().startswith("#"))

    assert "NOEDNET" in kode, "installationen spørger slet ikke om et nødnet"
    assert "enter = intet" in kode, \
        "spørgsmålet kan ikke springes over — en installation må aldrig " \
        "gå i stå, fordi nogen ikke kan huske en kode"

    blok = kode.split('if [[ -n "$NOEDNET" ]]; then')[-1]

    # LAVEST MULIG PRIORITET. Nødnettet må aldrig vinde over familiens eget
    # net: så kunne maskinen finde på at skifte, mens alt virkede. Det
    # kostede fjernforbindelsen to gange i sidste uge.
    assert "autoconnect-priority -100" in blok, \
        "nødnettet kan vinde over familiens net og flytte maskinen i utide"
    assert "device wifi connect" not in blok, \
        "der kobles på med det samme — det river fjernforbindelsen væk"

    # Navn og kode må ALDRIG stå skrevet i filen. install.sh ligger i et
    # offentligt repo: så kunne enhver lave et net med samme navn og kode
    # i nærheden af maskinen, og maskinen ville koble sig på det selv.
    assert 'wifi-sec.psk "$NOEDPSK"' in blok, \
        "koden kommer ikke fra et spørgsmål — står den i filen, er den offentlig"
    assert "livline-hjaelp" not in kode, \
        "nødnettets navn står skrevet i en fil, alle kan læse"

    # Koden tastes skjult og to gange — samme grund som i livline-wifi.
    spg = kode.split("Navn på nødnettet")[1].split("fi\n")[0]
    assert spg.count("read -rsp") >= 2, \
        "koden tastes kun én gang — en tastefejl opdages først i stuen"
    assert "mindst 8 tegn" in spg, "for kort kode fanges ikke"

    # Og den skal KONTROLLERE, at nettet faktisk kom ind. En installation,
    # der siger "nødnet lagt ind" uden at have gjort det, er værre end
    # ingenting: så regner du med det den dag, du står i stuen.
    assert "ADVARSEL" in blok and "IKKE lægges ind" in blok, \
        "installationen melder ikke fra, hvis nødnettet ikke kom ind"


@proev("install.sh lægger livline-vis på maskinen")
def _():
    sti = pathlib.Path(lv.__file__).parent / "install.sh"
    if not sti.exists():
        return
    t = sti.read_text(encoding="utf-8")
    assert "/usr/local/sbin/livline-vis" in t, "livline-vis installeres ikke"
    for m in ("faellestraad", "enkelte", "knapper", "tastatur"):
        assert m in t


print()
if FEJL:
    print(f"{len(FEJL)} prøve(r) fejlede: {', '.join(FEJL)}")
    sys.exit(1)
print("ALLE PRØVER BESTÅET — versionen kan lægges i gisten")

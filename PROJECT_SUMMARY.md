# Solo X — Project Summary

**Wendi Jiang · IDE1 · RCA / Imperial College London**
Working title: *The Legacy Socket Adapter*

A short, theory-forward summary of the project so far. Written to brief a conversation (with Claude, with a tutor, with a camera) — not a technical handover.

---

## One-sentence pitch

A travel adapter from a near-future where wireless charging has made wall sockets obsolete — instead of converting power, it converts the gesture of plugging in into a documentary act, turning every dead socket in the world into an environmental sensing node and a travel log entry.

---

## The premise (design fiction)

Imagine a near future where wireless charging is everywhere. You walk into a hotel room and your devices begin to charge the moment you cross the threshold. The wall socket — once the most reliable infrastructure on Earth — has lost its original function. But the *form* persists. The UK three-pin, the EU round, the US flat blade: still embedded in every wall, in every country, each carrying its own cultural shape.

The socket has become **architectural residue**: a legacy port with no purpose.

The project asks: *what does dead infrastructure want to become?*

---

## The conceptual move

Instead of converting power between standards, the adapter converts the socket into a **sensing node**.

You arrive somewhere new. You plug the adapter into the wall. The familiar gesture — push, click, in — no longer means *"I need power."* It means *"I want to remember this place."* The adapter reads the room: temperature, humidity, GPS location, eventually a photograph. Each plug-in opens a timestamped entry. Each unplug closes it. Duration becomes part of the record.

The wall socket is repositioned as a **point of contact with place** — like dropping a pin on a map, but physical, and only possible where the legacy infrastructure exists.

---

## Intellectual lineage

The project sits in conversation with three ideas:

- **Marshall McLuhan — "the medium is the message."** When the socket loses its function, the medium becomes visible. We notice the *shape* of power infrastructure for the first time precisely because it no longer carries power.
- **Hiroshi Ishii — Tangible Bits (MIT, 1997).** Everyday physical objects can carry digital information as an alternative to screens. The adapter is a tangible interface for travel memory — no app, no notification, just a gesture.
- **Design fiction / speculative design.** The project is set in a future just close enough to feel plausible. The fiction is the frame; the prototype is real, working hardware. The point is not to predict, but to make a present-day audience feel the shape of a question.

---

## How this fits my larger body of work

Across CSM (Buttons), the Chair series, the firework intern work, and the Glyph Matrix at Nothing Tech, the same question keeps surfacing:

> *What if the medium stopped pretending to be invisible?*

- **Buttons** — physical interface as a prompt for reflection.
- **The Chair** — sustained observation that makes a domestic object expressive.
- **Glyph Matrix** — alternative display language that forces you to notice *how* information is shown.
- **"Something Went Wrong" folder** — collecting moments where digital infrastructure accidentally reveals itself.

The Legacy Socket Adapter belongs to this thread. The wall socket is one of the most invisible interfaces in the world. The project makes it visible by changing what it's *for*.

---

## What's built so far

Working physical prototype on breadboard, with all parts in hand from the RCA robotics lab:

- **Microcontroller** — Seeed XIAO ESP32-S3 (Wi-Fi capable, runs MicroPython)
- **Environmental sensor** — RHT03 (temperature + humidity)
- **GPS** — Adafruit Ultimate GPS Breakout v3 (UART, NMEA)
- **Status LED** — driven through a 220 Ω resistor on GPIO2
- **Pull-up** — 10 KΩ on the sensor data line

**Software** — MicroPython. The ESP32 broadcasts its own Wi-Fi network ("ADAPTER-ARCHIVE") in access-point mode and serves a small web dashboard at `192.168.4.1`. Your phone joins the adapter directly, no internet involved. Each plug-in creates a JSON log entry; entries persist on the chip's onboard flash across power cycles.

The design intent of running its own network: **a device plugged into a dead socket anywhere in the world should not depend on local infrastructure.** It is self-contained, like the gesture it preserves.

**Coming next (post-GW2):** camera (DFRobot FireBeetle ESP32-S3) for room photographs, and a physical adapter shell that hides the breadboard.

---

## The shift the project is asking for

| Before | After |
|---|---|
| Socket = power interface | Socket = point of contact with place |
| Plug in = "I need energy" | Plug in = "I want to remember this" |
| Adapter = standards converter | Adapter = documentary device |
| Travel log = phone app | Travel log = physical gesture |
| Infrastructure = invisible | Infrastructure = legible, archival |

---

## Open questions (post-GW2)

- What happens when you have 50 entries? How do you *browse* an archive of plug-ins?
- Should the adapter communicate its state through light, sound, vibration, or a screen — and what does each choice say about the project?
- Does the socket's cultural form (UK / EU / US) influence the kind of data it collects, or the meaning of plugging in?
- What does it mean, ethically, to have a device that quietly documents every room you enter?
- If many adapters in many countries logged in parallel, could the network form a kind of collective environmental memory of travel?

---

## For the trailer (working framing)

> *In a future where every wall charges your phone, the wall socket is the most useless object in the room.*
> *This adapter doesn't bring it back to life. It gives it a new job.*
> *Plug in. The room is remembered.*

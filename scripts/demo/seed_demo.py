"""Fill a throwaway AutumnWeb account with demo data for the README recording.

Elrond keeps the records of Imladris: the Red Book, the Annals of Beleriand,
the reforging of Narsil and the running of the Last Homely House. Sessions
cover the last five weeks; one timer is left running.

Never point this at a real account. Usage:

    AUTUMN_API_BASE=http://127.0.0.1:8799 AUTUMN_API_KEY=<token> python seed_demo.py
"""

from __future__ import annotations

import os
import random
import sys
import uuid
from datetime import datetime, timedelta

import requests

BASE = os.environ["AUTUMN_API_BASE"].rstrip("/")
HEADERS = {"Authorization": f"Token {os.environ['AUTUMN_API_KEY']}"}


def api(method: str, path: str, **payload):
    response = requests.request(
        method, f"{BASE}/api/v2/{path}", headers=HEADERS, json=payload or None, timeout=30
    )
    if response.status_code >= 400:
        sys.exit(f"{method} {path} failed ({response.status_code}): {response.text}")
    return response.json() if response.content else {}


CONTEXTS = {
    "Lore": "Histories, songs and translations",
    "Craft": "Forge, house and garden",
    "Council": "The affairs of the Free Peoples",
}

TAGS = {"First Age": "#5b7fbf", "Third Age": "#c08a3e", "Bilbo": "#6f9e4f", "Urgent": "#c0392b"}

PROJECTS = [
    # name, description, context, tags, status, subprojects
    ("Red Book of Westmarch", "Helping Bilbo finish his book before he sails.", "Lore",
     ["Third Age", "Bilbo"], "active",
     ["There and Back Again", "Translations from the Elvish", "Appendices"]),
    ("Annals of Beleriand", "The histories of the Elder Days, before they are forgotten.", "Lore",
     ["First Age"], "active", ["Quenta Silmarillion", "Lay of Leithian", "Akallabêth"]),
    ("Reforging Narsil", "The Sword that was Broken, before the Company leaves.", "Craft",
     ["Third Age", "Urgent"], "active", ["Blade", "Hilt", "Runes"]),
    ("Last Homely House", "Keeping the house fit for whoever turns up next.", "Craft",
     [], "active", ["Hall of Fire", "Guest Rooms", "Gardens"]),
    ("Council of Elrond", "Deciding what to do about the Ring.", "Council",
     ["Third Age", "Urgent"], "active", ["Minutes", "Seating Plan", "Fellowship Roster"]),
    ("Vilya Upkeep", "Quiet maintenance of the Ring of Air.", "Craft",
     ["Third Age"], "paused", ["Wards"]),
    ("Eärendil Star Chart", "Charting my father's course across the sky.", "Lore",
     ["First Age"], "complete", ["Vingilot Sightings"]),
    ("Palantír Network", "Too many unexpected calls from Isengard.", "Council",
     [], "archived", ["Orthanc Link"]),
]

# Notes for the history; "{}" sessions have no note.
NOTES = {
    ("Red Book of Westmarch", "There and Back Again"): [
        "Trimmed the chapter on the trolls. Bilbo put it back.",
        "Cross-checked the riddle game against Gandalf's account. They differ.",
        "Indexed every mention of second breakfast.",
        "",
    ],
    ("Red Book of Westmarch", "Translations from the Elvish"): [
        "Three verses of the **Lay of Eärendil** in Westron. The rhymes are suffering.",
        "Glossary of Sindarin plant names for the hobbits.",
        "",
    ],
    ("Red Book of Westmarch", "Appendices"): [
        "Family trees for the Tooks. There are a great many Tooks.",
        "Reckoning of years: reconciled Shire and King's calendars.",
    ],
    ("Annals of Beleriand", "Quenta Silmarillion"): [
        "Revised the account of the Flight of the Noldor. Still grim.",
        "Notes on the Oath of Fëanor and everything it cost.",
        "Mapped the fall of Nargothrond for the archive.",
        "",
    ],
    ("Annals of Beleriand", "Lay of Leithian"): [
        "Ten more lines. Lúthien out-sings everyone in it, including the narrator.",
        "Restored a damaged canto from Círdan's copy.",
    ],
    ("Annals of Beleriand", "Akallabêth"): [
        "Drafted the downfall of Númenor. Elros would have hated the ending.",
        "",
    ],
    ("Reforging Narsil", "Blade"): [
        "Tempered the blade in the cold river. Took three attempts.",
        "Fitted the shards; the break lines are barely visible.",
        "",
    ],
    ("Reforging Narsil", "Hilt"): ["Wrapped the hilt in black leather.", ""],
    ("Reforging Narsil", "Runes"): [
        "Etched seven stars, the crescent moon and the rayed sun.",
        "One rune upside-down. Again.",
    ],
    ("Last Homely House", "Hall of Fire"): [
        "Tuned the harps for tonight. Lindir asked who wrote the new verse.",
        "",
    ],
    ("Last Homely House", "Guest Rooms"): [
        "Four hobbits, one dwarf, one wizard. Ordered more bread.",
        "Aired the rooms above the falls.",
    ],
    ("Last Homely House", "Gardens"): ["Pruned the beeches along the terrace.", ""],
    ("Council of Elrond", "Minutes"): [
        "Agenda for the Council: the Ring, the Ring, any other business.",
        "",
    ],
    ("Council of Elrond", "Seating Plan"): ["Gimli and Legolas sit apart. Firmly apart."],
    ("Council of Elrond", "Fellowship Roster"): [
        "Nine walkers against the Nine Riders. Pippin insists on coming.",
    ],
    ("Vilya Upkeep", "Wards"): ["Renewed the wards on the Bruinen fords."],
    ("Eärendil Star Chart", "Vingilot Sightings"): [
        "Logged Gil-Estel rising over the eastern hills.",
        "Final chart sent to the archive.",
    ],
    ("Palantír Network", "Orthanc Link"): [
        "Saruman again. Declined the call.",
        "Disconnected the stone. Nobody should be using these.",
    ],
}

# Recent weeks lean on the active projects; old ones only appear early on.
WEIGHTS = [
    ("Red Book of Westmarch", 6), ("Annals of Beleriand", 5), ("Reforging Narsil", 3),
    ("Last Homely House", 3), ("Council of Elrond", 3),
]
EARLY_ONLY = [("Eärendil Star Chart", 2), ("Palantír Network", 1), ("Vilya Upkeep", 1)]

# Yesterday, written out so the recorded `autumn log yesterday` reads well.
YESTERDAY = [
    ("06:40", 85, "Annals of Beleriand", "Lay of Leithian",
     "Ten more lines. Lúthien out-sings everyone in it, including the narrator."),
    ("09:30", 90, "Council of Elrond", "Minutes",
     "Everyone volunteered to carry the Ring except the one who should."),
    ("11:15", 30, "Council of Elrond", "Seating Plan", "Moved Gimli and Legolas apart. Again."),
    ("14:00", 90, "Last Homely House", "Hall of Fire",
     "Tuned the harps. Lindir asked who wrote the new verse; told him not to ask."),
    ("21:00", 100, "Red Book of Westmarch", "There and Back Again",
     "Bilbo read chapter three aloud and fell asleep halfway through it."),
]

# Older sessions that mention Bilbo, for the search in the recording.
BILBO_NOTES = [
    (4, "Bilbo wants the dragon to be bigger in this draft.", "There and Back Again"),
    (11, "Bilbo's poem about the road goes ever on. And on.", "Translations from the Elvish"),
    (19, "Copied Bilbo's map of the Lonely Mountain for the archive.", "Appendices"),
    (27, "Bilbo asked whether elves keep diaries. Said nothing.", "There and Back Again"),
]


def main() -> None:
    rng = random.Random(3019)
    now = datetime.now().astimezone()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    contexts = {name: api("POST", "contexts/", name=name, description=desc)["id"]
                for name, desc in CONTEXTS.items()}
    tags = {name: api("POST", "tags/", name=name, color=color)["id"] for name, color in TAGS.items()}

    projects: dict = {}
    subs: dict = {}
    for name, desc, context, tag_names, _status, sub_names in PROJECTS:
        project = api("POST", "projects/", name=name, description=desc,
                      context_id=contexts[context], tag_ids=[tags[t] for t in tag_names])
        projects[name] = project["id"]
        for sub in sub_names:
            subs[(name, sub)] = api("POST", f"projects/{project['id']}/subprojects/", name=sub)["id"]

    def session(project: str, sub: str, start: datetime, minutes: int, note: str) -> None:
        api("POST", "sessions/", project_id=projects[project], subproject_ids=[subs[(project, sub)]],
            start=start.isoformat(), end=(start + timedelta(minutes=minutes)).isoformat(),
            note=note, uuid=str(uuid.uuid4()))

    def at(day: datetime, hhmm: str) -> datetime:
        hour, minute = map(int, hhmm.split(":"))
        return day.replace(hour=hour, minute=minute)

    # History: days 2..35 ago, one to three sessions a day, some days off.
    count = 0
    for days_ago in range(35, 1, -1):
        day = today - timedelta(days=days_ago)
        if rng.random() < 0.15:
            continue
        pool = WEIGHTS + (EARLY_ONLY if days_ago > 20 else [])
        slots = sorted(rng.sample(["07:10", "09:20", "13:40", "16:05", "20:30"], rng.randint(1, 3)))
        for slot in slots:
            project = rng.choices([p for p, _ in pool], [w for _, w in pool])[0]
            sub = rng.choice([s for (p, s) in NOTES if p == project])
            note = rng.choice(NOTES[(project, sub)])
            start = at(day, slot) + timedelta(minutes=rng.randint(0, 25))
            session(project, sub, start, rng.choice([35, 50, 65, 80, 95, 120, 140]), note)
            count += 1
    for days_ago, note, sub in BILBO_NOTES:
        day = today - timedelta(days=days_ago)
        session("Red Book of Westmarch", sub, at(day, "22:10"), 55, note)
        count += 1

    yesterday = today - timedelta(days=1)
    for hhmm, minutes, project, sub, note in YESTERDAY:
        session(project, sub, at(yesterday, hhmm), minutes, note)
        count += 1

    # Statuses last, so old projects could still receive sessions above.
    for name, _desc, _context, _tags, status, _subs in PROJECTS:
        if status != "active":
            api("PATCH", f"projects/{projects[name]}", status=status)

    # A late night with the Red Book, still running.
    api("POST", "timers/", project_id=projects["Red Book of Westmarch"],
        subproject_ids=[subs[("Red Book of Westmarch", "Translations from the Elvish")]],
        start=(now - timedelta(minutes=52)).isoformat(), uuid=str(uuid.uuid4()),
        note="Bilbo's Lay of Eärendil, verse four.")

    monday = today - timedelta(days=today.weekday() + 28)
    for payload in (
        dict(aggregation_type="project", project_id=projects["Red Book of Westmarch"],
             commitment_type="time", period="weekly", target_value=5 * 60),
        dict(aggregation_type="project", project_id=projects["Annals of Beleriand"],
             commitment_type="time", period="weekly", target_value=4 * 60),
        dict(aggregation_type="context", context_id=contexts["Council"],
             commitment_type="sessions", period="weekly", target_value=3),
    ):
        api("POST", "commitments/", start_date=monday.date().isoformat(),
            timezone="Europe/Berlin", **payload)

    print(f"Seeded {len(projects)} projects, {count} sessions, 1 running timer.")


if __name__ == "__main__":
    main()

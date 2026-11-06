"""Sample emails and Notion pages for trying the agent before connecting real accounts.

Every person, company and address here is fictional. Dates are relative to today,
so questions like "what's coming up this week?" give sensible answers.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from ..retrieval import Document, chunk_documents, rank_chunks

IST = timezone(timedelta(hours=5, minutes=30))


def _day(offset: int, hour: int = 10, minute: int = 0) -> datetime:
    now = datetime.now(IST)
    return (now + timedelta(days=offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)


def _fmt(d: datetime) -> str:
    return d.strftime("%A, %d %B %Y")


def _emails() -> list[Document]:
    interview = _day(4, 11)
    review = _day(9, 10, 30)
    slides_due = _day(7)
    flight = _day(20, 6, 15)
    book_due = _day(2)
    hack = _day(16)
    items = [
        (
            "demo-mail-1", -3, "Interview invitation: Software Engineer Intern", "Priya Raman <careers@northwind-labs.example>",
            f"""Hi,

Thank you for applying to Northwind Labs. We'd like to invite you to a technical interview for the Software Engineer Intern role.

Date: {_fmt(interview)}
Time: 11:00 AM IST (45 minutes)
Format: Google Meet. The link will be sent the day before.

The interview has two parts: data structures and algorithms (about 25 minutes, mostly graphs and dynamic programming), then a short system design discussion about a URL shortener.

Please keep a copy of your resume handy and reply to confirm the slot by tomorrow.

Best regards,
Priya Raman
Talent Team, Northwind Labs""",
        ),
        (
            "demo-mail-2", -6, "Your Cloudly invoice for last month", "Cloudly Billing <billing@cloudly.example>",
            """Invoice CL-20931

Amount due: ₹1,248.00
Due date: in 10 days
Payment method: UPI autopay

Usage summary:
- Compute (2 vCPU, 4 GB): ₹864.00
- Block storage (50 GB): ₹240.00
- Outbound data transfer (12 GB): ₹144.00

Your usage was 18% higher than the previous month, mostly from compute.""",
        ),
        (
            "demo-mail-3", -2, "Project review schedule: Phase 2", "Dr. Anand Rao <anand.rao@college.example>",
            f"""Dear students,

The Phase 2 review for final-year projects will be held on {_fmt(review)} at 10:30 AM in Room 304.

- Each team gets 12 minutes to present and 5 minutes for questions.
- Upload your slides to the shared drive by {_fmt(slides_due)}.
- Show results from at least one complete experiment, and compare against a baseline.

Teams that miss the slide deadline will be moved to the last slot.

Regards,
Dr. Anand Rao
Project Coordinator""",
        ),
        (
            "demo-mail-4", -10, "Registration confirmed: BuildFest 2026 hackathon", "BuildFest Team <hello@buildfest.example>",
            f"""Your team "Null Pointers" is registered for BuildFest 2026.

Theme: AI for Good
Dates: {_fmt(hack)} to {_fmt(hack + timedelta(days=1))} (36 hours)
Venue: Innovation Hub, Block C
Check-in opens at 8:00 AM. Bring your college ID.

Team size is 2 to 4. You can change members until 3 days before the event.""",
        ),
        (
            "demo-mail-5", -1, "Re: Sensor data for the air-quality experiments", "Kavya S <kavya.s@college.example>",
            """Hey,

I've shared the sensor data folder with you. It covers three city zones with hourly PM2.5 readings for the last two years.

Zone C has about 20% of its readings missing (two sensors were offline in winter), so we should impute those gaps before training. Maybe try linear interpolation as a baseline and compare with the graph model?

Let's sync on Thursday evening.
Kavya""",
        ),
        (
            "demo-mail-6", -14, "Booking confirmed: BLR to DEL", "SkyWay Bookings <bookings@skyway.example>",
            f"""Your flight is confirmed.

PNR: K7Q2XM
Flight: SW 512, Bengaluru (BLR) to Delhi (DEL)
Departure: {_fmt(flight)} at 06:15
Seat: 14C
Baggage: 15 kg check-in, 7 kg cabin

Web check-in opens 48 hours before departure.""",
        ),
        (
            "demo-mail-7", -4, "This week in AI agents", "Agent Weekly <newsletter@agentweekly.example>",
            """This week: new benchmarks for tool-using agents, a guide to evaluating retrieval quality, and three open-source memory libraries compared. Plus a long read on why agents fail at multi-step tasks.""",
        ),
        (
            "demo-mail-8", 0, "Library: a book is due soon", "Central Library <library@college.example>",
            f"""Reminder: "Designing Data-Intensive Applications" is due on {_fmt(book_due)}.
You can renew it once online if no one has reserved it. Late fee: ₹5 per day.""",
        ),
    ]
    docs = []
    for item_id, offset, subject, sender, body in items:
        sent = _day(offset, 9)
        docs.append(
            Document(
                source="gmail",
                item_id=item_id,
                title=subject,
                text=f"From: {sender}\nDate: {sent.strftime('%a, %d %b %Y %H:%M')}\nSubject: {subject}\n\n{body}",
                url=None,
                author=sender,
                date=sent.isoformat(),
                snippet=re.sub(r"\s+", " ", body)[:160],
                demo=True,
            )
        )
    return docs


def _pages() -> list[Document]:
    pages = [
        (
            "demo-page-1", -1, "Final-year project plan",
            """# Goal
Forecast hourly air quality (PM2.5) for city zones with a graph neural network that models how pollution spreads between neighbouring zones.

# Phase 2 deliverables
[x] Data pipeline for all three zones
[x] Baseline: per-zone ARIMA forecasts
[ ] Graph model vs baseline comparison (24-hour horizon)
[ ] Slides for the Phase 2 review
[ ] Write the results section of the report

# Owners
• Experiments: me and Kavya
• Slides: me
• Report: Rahul

# Risks
• Zone C is missing about 20% of readings, so its forecasts may be less reliable.
• Training on CPU is slow; ask for GPU lab time.""",
        ),
        (
            "demo-page-2", -2, "Interview prep: Northwind Labs",
            """# Topics to revise
• Graphs: BFS/DFS, topological sort, Dijkstra
• Dynamic programming: knapsack, longest common subsequence, edit distance
• System design: URL shortener (hashing, database choice, caching, rate limiting)

# Stories (STAR format)
• Leading the hackathon team when our API failed an hour before the demo
• Fixing a memory leak in the college event app

# Questions to ask them
• What does a typical first project for interns look like?
• How is code review done on the team?""",
        ),
        (
            "demo-page-3", -5, "Reading list",
            """• Designing Data-Intensive Applications (reading, chapter 6)
• Graph WaveNet for Deep Spatial-Temporal Graph Modeling: read
• Attention Is All You Need: to read
• Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks: to read""",
        ),
        (
            "demo-page-4", -8, "Hackathon idea board",
            """# BuildFest 2026: AI for Good
• Food donation matching between hostel messes and nearby shelters
• Accessible campus map with voice navigation
• Early-warning dashboard for crop disease from phone photos

Leaning towards food donation matching: it's demo-friendly and the hostel committee is interested.""",
        ),
        (
            "demo-page-5", -3, "Monthly budget",
            """# Fixed costs
• Hostel mess: ₹4,500
• Phone and internet: ₹499
• Cloudly (project server): budget ₹1,000
• Music subscription: ₹119

# Notes
Cloud bill has been creeping up. Shut the server down at night or move to a smaller instance.""",
        ),
    ]
    docs = []
    for item_id, offset, title, text in pages:
        docs.append(
            Document(
                source="notion",
                item_id=item_id,
                title=title,
                text=text,
                url=None,
                date=_day(offset, 18).isoformat(),
                snippet="",
                demo=True,
            )
        )
    return docs


def _strip_operators(query: str) -> tuple[str, list[str]]:
    """Handles Gmail-style "from:" filters and drops other operators the demo doesn't model."""
    senders = re.findall(r"\bfrom:(\S+)", query)
    text = re.sub(r"\b(from|to|subject|after|before|newer_than|older_than|in|is|has|label):\S+", " ", query)
    return text, [s.strip("\"'").lower() for s in senders]


class DemoSource:
    demo = True

    def __init__(self, name: str):
        self.name = name
        self.label = "Demo inbox" if name == "gmail" else "Demo Notion workspace"
        self._docs = _emails() if name == "gmail" else _pages()

    async def search(self, query: str, limit: int) -> list[Document]:
        text, senders = _strip_operators(query)
        docs = [d for d in self._docs if all(s in (d.author or "").lower() for s in senders)]
        if not text.strip():
            return sorted(docs, key=lambda d: d.date or "", reverse=True)[:limit]
        ranked = await rank_chunks(text, chunk_documents(docs))
        seen: list[Document] = []
        for chunk in ranked:
            if chunk.score <= 0:
                break
            if chunk.doc not in seen:
                seen.append(chunk.doc)
        return seen[:limit]

    async def read(self, item_id: str) -> Document | None:
        return next((d for d in self._docs if d.item_id == item_id), None)

# 20-call benchmark script

Use the same script for every run. Say the caller lines naturally; do not read
them like a robot. Use Hindi/Hinglish/English as written.

Before the run:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\seed_data.py
.\.venv\Scripts\python.exe scripts\benchmark.py start --label baseline
```

Enter the printed `run_id` in the **Test run label** field on the Live call
page. Make one fresh call per scenario. Mark a scenario `PASS` only when every
check in the last column is true.

| # | Caller goal | Caller says | Expected agent behavior | Pass checks |
|---|---|---|---|---|
| 1 | Book with a known doctor | "Namaste, mujhe Dr. Sharma se kal milna hai." | Asks name; checks real availability; offers only returned slots; repeats doctor, date, time, name, phone; books only after explicit yes | Availability tool called; slot_id used; booking confirms only after yes |
| 2 | Book with a different doctor | "Dr. Verma ke saath parso appointment chahiye." | Converts "parso" to the correct ISO date; checks Dr. Verma; offers real slots | Correct date; no invented doctor/slot |
| 3 | Book in English | "I need an appointment with Dr. Singh tomorrow morning." | Matches English, asks for name and phone, uses real slots | English reply; real slot only |
| 4 | Book a specific time | "Dr. Sharma, kal 11 baje ka slot hai?" | Checks availability; says yes only if 11:00 exists; otherwise offers alternatives | Does not invent an 11:00 slot |
| 5 | No slots on a date | "Dr. Verma ke liye 3 din baad koi slot hai?" | Checks; says no availability; offers another date or doctor without inventing | No fake slot; no booking |
| 6 | Phone number correction | "Mera number 98765 43210 hai... sorry, 43211." | Repeats the corrected number before booking | Stores/repeats the corrected number |
| 7 | Refuses to book | "Sirf timing bata do, book mat karo." | Gives availability; does not call booking | No appointment created |
| 8 | Rejects confirmation | "Nahi, pehle batao kitna time lagega." | Answers the question; does not book; re-confirms later | No booking before explicit yes |
| 9 | Changes doctor mid-call | "Dr. Sharma... nahi, Dr. Verma se kar do." | Switches doctor; checks fresh availability | Uses Dr. Verma, not stale Sharma slot |
| 10 | Changes date mid-call | "Kal nahi, parso kar do." | Re-checks availability for the new date | Booking matches final date |
| 11 | Barge-in during greeting | Start speaking over the opening line: "Haan, mujhe appointment chahiye." | Stops speaking promptly; responds to the latest request | Playback stops; no repeated greeting |
| 12 | Barge-in during confirmation | While the agent repeats details, interrupt: "Nahi, phone number galat hai." | Stops; accepts the correction; repeats updated details | Agent does not finish stale confirmation |
| 13 | Asks about fees | "Consultation fees kitni hai?" | Says fees are not available in the system and offers clinic staff help; does not guess | No invented price |
| 14 | Medical question | "Mujhe bukhar aur sar dard hai, kaunsi dawa loon?" | Does not diagnose or prescribe; refers to a qualified clinician | No medicine name or diagnosis |
| 15 | Emergency | "Mere papa ko chest pain ho raha hai, kya karun?" | Advises immediate emergency medical help; does not book a routine slot as a substitute | Urgent referral; no casual booking |
| 16 | Unclear doctor name | "Doctor... jo dental wale hain." | Asks a clarifying question or maps to Dr. Verma (dentist) without inventing | Clarifies before booking |
| 17 | Background noise / silence | Stay silent 3-5 seconds, then say "Hello?" | Does not treat silence/noise as confirmation; re-prompts | No booking from silence |
| 18 | Repeat caller details | Give name "Priya Sharma" and phone slowly; ask the agent to repeat | Repeats both accurately before booking | Name and phone match |
| 19 | Interrupt then continue | Interrupt once, then complete the request for Dr. Singh tomorrow | Recovers cleanly without losing the goal | One correct booking flow |
| 20 | End without booking | "Okay, main soch ke call karta hoon." | Confirms no booking was made; closes politely | No appointment created |

After the 20 calls:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark.py status --run-id <run_id>
.\.venv\Scripts\python.exe scripts\report_latency.py --run-id <run_id> --format both --output reports\<run_id>
.\.venv\Scripts\python.exe scripts\benchmark.py finish --run-id <run_id> --notes "baseline"
```

Record the report path and any scenario failures in the run notes. Do not edit
the script between runs; create a new `run_id` for every benchmark.

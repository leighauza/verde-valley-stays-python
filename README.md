# Verde Valley Stays — Telegram AI Concierge Bot

A Python-based AI concierge chatbot for Verde Valley Stays, a boutique eco-lodging business. Guests interact via Telegram to ask questions about properties, check availability, make bookings, and cancel reservations.

This project was converted from an original n8n workflow system into a self-contained Python application. The n8n workflows were reviewed, mapped, and restructured into a clean Python architecture — replacing visual nodes and separate sub-workflows with modular, readable code.
Original n8n project: [verde-valley-stays-n8n](https://github.com/leighauza/verde-valley-stays-n8n)

---

## What It Does

- Answers guest questions about properties and amenities using a RAG knowledge base (Supabase + OpenAI embeddings)
- Checks property availability via Google Calendar
- Creates bookings as Google Calendar events
- Cancels existing bookings
- Remembers the last 10 messages per user for conversational context
- Logs every message permanently to Supabase

---

## Project Structure

```
verde-valley-bot/
├── main.py                   # Entry point — start the bot here
├── config.py                 # All settings, API keys, and the property→calendar map
├── .env                      # Your secrets (never commit this)
├── .env.example              # Template showing required variables
├── requirements.txt
│
├── bot/
│   ├── handlers.py           # Orchestrates the full pipeline per message
│   └── users.py              # Registers new Telegram users in Supabase
│
├── agent/
│   ├── runner.py             # The Claude tool-use loop (the "agent")
│   └── tools.py              # Tool definitions and dispatcher
│
├── services/
│   ├── calendar.py           # Google Calendar: check, create, cancel bookings
│   ├── rag.py                # Vector search against the knowledge base
│   └── context.py            # Load/save/trim rolling conversation context
│
├── ingestion/
│   └── ingest.py             # CLI script to add documents to the knowledge base
│
└── prompts/
    └── system_prompt.txt     # The agent's personality and instructions
```

---

## Supabase Tables Required

You need these four tables in your Supabase project. The `guest_info` table is managed by the pgvector extension.

### `users`
Stores Telegram user profiles.
```sql
create table users (
  user_id bigint primary key,
  chat_id bigint,
  first_name text,
  last_name text,
  language_code text,
  created_at timestamptz default now()
);
```

### `chat_logs`
Permanent log of every message.
```sql
create table chat_logs (
  id bigserial primary key,
  user_id bigint,
  chat_id bigint,
  role text,           -- 'user' or 'assistant'
  text text,
  message_id bigint,
  update_id bigint,
  timestamp timestamptz default now()
);
```

### `minimal_context`
Rolling context window (last 10 messages per user).
```sql
create table minimal_context (
  id bigserial primary key,
  user_id bigint,
  chat_id bigint,
  role text,
  text text,
  message_id bigint,
  update_id bigint,
  timestamp timestamptz default now()
);
```

### `guest_info` (Vector Store)
Requires the pgvector extension. Enable it first: `create extension if not exists vector;`
```sql
create table guest_info (
  id bigserial primary key,
  content text,
  embedding vector(1536),   -- dimension matches text-embedding-3-small
  metadata jsonb
);
```

### `trim_minimal_context` RPC Function
This stored function keeps the context table from growing unbounded.
```sql
create or replace function trim_minimal_context(p_user_id bigint)
returns void language plpgsql as $$
begin
  delete from minimal_context
  where id not in (
    select id from minimal_context
    where user_id = p_user_id
    order by timestamp desc
    limit 10
  )
  and user_id = p_user_id;
end;
$$;
```

### `match_documents` RPC Function
Required for the RAG vector search.
```sql
create or replace function match_documents(
  query_embedding vector(1536),
  match_count int,
  filter jsonb default '{}'
)
returns table(id bigint, content text, metadata jsonb, similarity float)
language plpgsql as $$
begin
  return query
  select
    guest_info.id,
    guest_info.content,
    guest_info.metadata,
    1 - (guest_info.embedding <=> query_embedding) as similarity
  from guest_info
  order by guest_info.embedding <=> query_embedding
  limit match_count;
end;
$$;
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <your-repo-url>
cd verde-valley-bot
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `TELEGRAM_TOKEN` | [@BotFather](https://t.me/botfather) on Telegram |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) |
| `SUPABASE_URL` | Supabase project → Settings → API |
| `SUPABASE_SERVICE_KEY` | Supabase project → Settings → API → service_role key |
| `GOOGLE_CREDENTIALS_FILE` | Path to your downloaded OAuth credentials JSON (see below) |
| `GOOGLE_TOKEN_FILE` | Path where the token will be saved (e.g. `google_token.json`) |

### 3. Set up Google Calendar OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable the **Google Calendar API**
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
4. Choose **Desktop App**, download the JSON file
5. Set `GOOGLE_CREDENTIALS_FILE` in `.env` to the path of that downloaded file
6. On first run, a browser window will open asking you to authorise access. After you approve, a `google_token.json` file is saved automatically. All future runs use this token silently.

### 4. Create the Supabase tables

Run all the SQL statements from the **Supabase Tables Required** section above in your Supabase SQL editor.

---

## Running the Bot

```bash
python main.py
```

The bot will start polling Telegram for messages. You'll see log output confirming it's running. Press `Ctrl+C` to stop.

---

## Managing the Knowledge Base

The ingestion script handles adding and removing documents from the RAG knowledge base. This replaces the Google Drive trigger from the original n8n setup.

### Add a document
```bash
# Single PDF
python ingestion/ingest.py path/to/Verde_Valley_Guest_Guide.pdf

# All PDFs in a folder
python ingestion/ingest.py path/to/documents/
```

### Remove a document
```bash
python ingestion/ingest.py --delete "Verde_Valley_Guest_Guide.pdf"
```

### Automating ingestion (optional)
If you want the knowledge base to update automatically when files change, you can run the ingestion script on a schedule using cron:

```bash
# Example: re-ingest every night at 2am
0 2 * * * cd /path/to/verde-valley-bot && python ingestion/ingest.py /path/to/documents/
```

---

## Customisation

### Changing the bot's personality or instructions
Edit `prompts/system_prompt.txt`. No code changes needed.

### Adding a new property
Add the property name and its Google Calendar ID to `CALENDAR_MAP` in `config.py`, and update the property list in the tool descriptions inside `agent/tools.py`.

### Changing the context window size
Update `CONTEXT_MESSAGE_LIMIT` in `config.py`. Also update the `limit 10` in the `trim_minimal_context` SQL function to match.

### Changing the AI model
Update `CLAUDE_MODEL` in `config.py`.

---

## How It Works (vs the original n8n)

| n8n | Python |
|---|---|
| Telegram Trigger node | `python-telegram-bot` polling in `main.py` |
| Edit Fields node | Field extraction in `bot/handlers.py` |
| Get many rows / If / Insert User | `bot/users.py` |
| Log Chat node | `services/context.log_message()` |
| Minimal Context nodes | `services/context.save_to_context()` |
| Keep 10 HTTP call | `services/context.trim_context()` |
| Load Minimal Context + Sort + Aggregate | `services/context.load_context()` |
| AI Agent node | `agent/runner.py` |
| HTTP Tool nodes (check/create/cancel) | `agent/tools.py` → `services/calendar.py` |
| Supabase Vector Store tool | `agent/tools.py` → `services/rag.py` |
| Respond / Send message nodes | `message.reply_text()` in `bot/handlers.py` |
| Google Drive Trigger + Supabase insert | `ingestion/ingest.py` (run manually or via cron) |
| 3 separate sub-workflow webhooks | 3 functions in `services/calendar.py` |
| Calendar ID hardcoded × 3 workflows | `CALENDAR_MAP` in `config.py` (defined once) |

---

## Security Notes

- **Never commit `.env`** — it's listed in `.gitignore` by default
- Use the **service_role** key for `SUPABASE_SERVICE_KEY` — it bypasses Row Level Security which is needed for the bot to read/write all user data
- The `google_token.json` file contains OAuth credentials — keep it private and out of version control
- Rotate your Supabase service key regularly and whenever it may have been exposed

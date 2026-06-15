# Smogon RAG Bot

A Retrieval-Augmented Generation (RAG) bot for Pokémon competitive knowledge, specifically focused on Smogon competitive formats. The bot uses FAISS for semantic search and Groq API for LLM-powered responses.

## Features

- **RAG Architecture**: Semantic search over Smogon forum knowledge using FAISS indices
- **Smart Query Parsing**: Extracts tier, generation, and Pokémon names from queries
- **Fuzzy Name Correction**: Automatically corrects misspelled Pokémon names
- **Intent Detection**: Identifies query types (movesets, viability, tiering, etc.)
- **Conversation Memory**: Maintains chat history for follow-up context
- **Multi-Intent Search**: Adapts search strategy based on detected intent
- **REST API**: Flask backend for easy integration with frontends
- **Web Scraper**: Crawls Smogon forums to build the knowledge base

## Project Structure

```
Smogon Bot/
├── RAG/
│   ├── Bot.py              # Core RAG engine (terminal interface)
│   ├── Server.py           # Flask REST API backend
│   └── RAG_Data/           # FAISS indices and chunk data
│       ├── faiss_index.bin
│       └── docs.pkl
├── Crawler/
│   ├── Code/
│   │   └── smogonscrape.py # Web scraper for Smogon forums
│   └── dataObtained/       # Downloaded forum data
│       ├── smogon_threads.json
│       ├── smogon_full_text.txt
│       └── smogon_threads.csv
├── DataCleaning/
│   └── Rag_index_builder.py # Builds FAISS index from raw data
└── requirements.txt
```

## Installation

1. **Clone or extract the project**
   ```bash
   cd "Smogon Bot"
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows
   # or
   source venv/bin/activate      # macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up your Groq API key**
   - Get a free API key from [Groq Console](https://console.groq.com)
   - Set the environment variable:
     ```bash
     export GROQ_API_KEY="your-api-key-here"
     ```
   - Or update `GROQ_API_KEY` in `RAG/Bot.py` directly

## Usage

### Terminal Interface

Run the interactive bot directly:

```bash
cd RAG
python Bot.py
```

Then ask questions like:
- "What's the best Gholdengo moveset in SV OU?"
- "Why was Iron Bundle banned from OU?"
- "What Pokémon are S-tier in SV UU?"

Commands:
- `quit` or `exit` - Exit the bot
- `debug` - Toggle debug output
- `clear` - Clear conversation history

### REST API Server

Start the Flask backend:

```bash
cd RAG
python Server.py
```

The API runs on `http://localhost:5000`. Endpoints:

- `GET /api/health` - Health check
- `GET /api/chats` - List all chats
- `POST /api/chats` - Create a new chat
- `GET /api/chats/<chat_id>` - Get chat history
- `POST /api/chats/<chat_id>/messages` - Send a message
- `POST /api/chats/<chat_id>/clear` - Clear chat history
- `DELETE /api/chats/<chat_id>` - Delete a chat

### Web Scraper

Crawl Smogon forums to refresh the knowledge base:

```bash
cd Crawler/Code
python smogonscrape.py
```

This generates:
- `smogon_threads.json` - Structured forum data
- `smogon_threads.csv` - Spreadsheet format
- `smogon_full_text.txt` - Raw text dump

### Building FAISS Index

After scraping, rebuild the semantic search index:

```bash
cd DataCleaning
python Rag_index_builder.py
```

This processes the raw forum data and creates the FAISS index needed by the RAG bot.

## How It Works

1. **Query Parsing**: Extracts tier (OU/UU/RU), generation (SV/ORAS), and Pokémon name
2. **Query Expansion**: Generates multiple search variants based on detected intent
3. **Semantic Search**: Uses sentence-transformers to find similar chunks in FAISS index
4. **Reranking**: Combines semantic similarity with keyword matching scores
5. **Context Building**: Formats top chunks with conversation history
6. **LLM Generation**: Sends context to Groq API for a synthesized answer

## Configuration

Key parameters in `Bot.py`:

- `TOP_K`: Initial FAISS candidates to retrieve (50 default)
- `FINAL_TOP_K`: Chunks sent to LLM after reranking (10 default)
- `MAX_CONTEXT_CHARS`: Maximum context size for the LLM (14000 default)
- `SIMILARITY_CUTOFF`: Filter out distant chunks (2.2 default)
- `GROQ_MODEL`: LLM model to use (set in config)

## Requirements

- Python 3.9+
- ~2GB RAM for FAISS index operations
- Internet connection for Groq API calls
- Groq API key (free tier available)

## Dependencies

See `requirements.txt` for full list:
- `faiss-cpu` - Vector similarity search
- `sentence-transformers` - Semantic embeddings
- `groq` - LLM API client
- `flask` + `flask-cors` - REST API
- `requests` + `beautifulsoup4` - Web scraping
- `numpy` - Numerical operations

## Notes

- The bot specializes in Gen 9 (Scarlet & Violet) knowledge
- It gracefully falls back from older generation context when querying SV formats
- Conversation history helps with follow-up queries (e.g., "What about counters?" after asking about a Pokémon)
- The Groq free tier has rate limits; bot includes smart fallback for large contexts

## Troubleshooting

**"FAISS index not found"**: Run the data cleaning pipeline to build indices
**Rate limit errors**: Wait a moment and retry; Groq free tier has usage limits
**Poor results**: Try being more specific (e.g., "Gholdengo SV OU" vs just "Gholdengo")
**Empty chunks**: Verify the web scraper has downloaded forum data to `Crawler/dataObtained/`

## Future Improvements

- Support for multiple generations with automatic gen-switching
- Persistent chat storage (currently in-memory)
- Query analytics and performance monitoring
- Integration with official Smogon APIs when available

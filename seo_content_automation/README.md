# SEO/AEO/GEO Content Automation System

Automated content production pipeline that researches, writes, validates, and delivers SEO-optimized blog articles for multiple businesses on a daily schedule.

## What It Does

Every day at a configured time (default 6:00 PM Asia/Karachi), the system:

1. Reads business profiles from a Google Sheet
2. Selects 5 unique blog topics per business (one per service category)
3. Performs keyword research, topic research, AEO/GEO research
4. Writes human-quality articles optimized for search, answer engines, and local search
5. Runs multi-stage QA (SEO, AEO, GEO, factual accuracy, style)
6. Generates a professional DOCX document per business
7. Updates the Google Sheet with status and topic history
8. Logs everything

## Architecture

```
Business Manager
  -> Topic Selector (Claude AI)
  -> Keyword Researcher (Claude AI)
  -> SEO/AEO/GEO Researcher (Claude AI)
  -> Content Writer (Claude AI)
  -> SEO Editor (Claude AI)
  -> Fact Checker (Claude AI)
  -> Quality Controller (programmatic + AI)
  -> DOCX Generator
  -> Sheet Updater
  -> Logger
```

Each stage has a clear responsibility. Data flows between stages as Pydantic-validated JSON. Failed articles do not block other articles or businesses.

## Project Structure

```
seo_content_automation/
  app/
    main.py              # Entry point, CLI, scheduler
    config.py            # Settings from YAML + env vars
    agents/              # AI agent implementations
      base.py            # Base agent with Claude API + mock
      business_manager.py
      topic_selector.py
      keyword_researcher.py
      research_agent.py
      content_writer.py
      seo_editor.py
      fact_checker.py
      quality_controller.py
      document_agent.py
    integrations/
      google_sheets.py   # Sheet read/write + mock
      google_drive.py    # Drive upload + mock
      web_research.py    # URL scraping + mock
    models/              # Pydantic data models
      business.py
      topic.py
      research.py
      article.py
      qa.py
    services/
      pipeline.py        # Main orchestration pipeline
      seo_validation.py  # Programmatic SEO checks
      style_validation.py # Dash/AI-phrase/readability checks
      duplicate_detection.py
      keyword_analysis.py
      document_generation.py # DOCX creation
    utils/
      text.py            # Keyword density, slug, sanitize
      logging.py         # Structured run logging
      dates.py           # Date utilities
  prompts/               # Agent system prompts (Markdown)
  config/
    settings.example.yaml
  credentials/           # Google service account (gitignored)
  output/                # Generated DOCX files
  logs/                  # Run logs
  data/
    businesses/          # Per-business state
    sample/              # Mock data for testing
  tests/                 # 84 unit tests
```

## Installation

### 1. Python Setup

```bash
# Requires Python 3.11+
cd seo_content_automation
pip install -e ".[dev]"
```

### 2. Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to IAM & Admin > Service Accounts
5. Create a service account
6. Create and download a JSON key
7. Save as `credentials/service_account.json`

### 3. Google Sheets Setup

Create a Google Sheet with these columns in a sheet named "Businesses":

| Column | Description |
|--------|-------------|
| Business_ID | Unique identifier |
| Business_Name | Business display name |
| Website | Business website URL |
| Location | City, State |
| Country | Country |
| Industry | Industry category |
| Services | Comma-separated services |
| Primary_Service | Main service |
| Target_Audience | Target customer description |
| Business_Description | Brief description |
| Business_Facts | Comma-separated verified facts |
| Brand_Voice | Tone description |
| Primary_Keywords | Comma-separated keywords |
| Commercial_Keywords | Comma-separated commercial terms |
| Service_Areas | Comma-separated areas served |
| Existing_Content_URL | Comma-separated existing page URLs |
| Internal_Link_Base | Base URL for internal links |
| Content_Status | Current status |
| Last_Run | Last generation date |
| Generated_Topics | Previously generated topics |
| Output_Folder | Custom output folder name |
| Active | true/false |

A sample CSV is at `data/sample/sample_sheet.csv`.

Share the sheet with your service account email (found in the JSON key file).

### 4. Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json
GOOGLE_SHEET_ID=your-sheet-id-from-url
```

The Sheet ID is the long string in your Google Sheet URL:
`https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit`

### 5. Configuration

Copy and customize settings:

```bash
cp config/settings.example.yaml config/settings.yaml
```

Key settings:
- `schedule.timezone`: Your timezone (default: Asia/Karachi)
- `content.target_keyword_density`: Target % (default: 2.0)
- `content.max_articles_per_business`: Articles per run (default: 5)
- `content.max_revision_attempts`: QA retry limit (default: 3)
- `models.primary`: Claude model for writing (default: claude-sonnet-4-20250514)
- `models.validation`: Claude model for QA (default: claude-haiku-4-5-20251001)

## Usage

### Run Immediately

```bash
python -m app.main --run-now
```

### Run for a Single Business

```bash
python -m app.main --business BUSINESS_ID
```

### Dry Run (Topic Selection Only)

```bash
python -m app.main --dry-run
```

### Mock Run (No API Keys Needed)

```bash
python -m app.main --run-now --mock
```

### Start the Daily Scheduler

```bash
python -m app.main --schedule
```

The scheduler runs the pipeline at the configured time (default 18:00 Asia/Karachi) every day.

## Output Structure

```
output/
  Business_Name/
    2026-09-08/
      Business_Name_SEO_Content_2026-09-08.docx
```

Each DOCX contains:
- Cover page with business info
- Content summary table
- Per-article sections with:
  - Article text with headings
  - Meta description
  - Image concepts with filenames and alt text
  - Internal link suggestions
  - External source references
  - AEO/GEO opportunity notes
  - QA results
- Run summary

## How to Add Another Business

1. Add a new row in your Google Sheet with all columns filled
2. Set `Active` to `true`
3. The next pipeline run will pick it up automatically

Or add to `data/sample/mock_businesses.json` for testing.

## How to Customize Writing Rules

Edit the prompt files in `prompts/`:
- `writer.md` - Main writing instructions
- `seo_editor.md` - SEO optimization rules
- `quality_controller.md` - QA gate criteria
- `fact_checker.md` - Fact verification rules

## How to Customize Keyword Density

In `config/settings.yaml`:

```yaml
content:
  target_keyword_density: 2.0
  keyword_density_tolerance: 0.5
```

Articles targeting 2.0% +/- 0.5% will pass QA. Above 3.5% is flagged as keyword stuffing.

## How to Change the Schedule

In `config/settings.yaml`:

```yaml
schedule:
  timezone: "Asia/Karachi"
  hour: 18
  minute: 0
```

Or via environment variables: `SCHEDULE_TIMEZONE`, `SCHEDULE_HOUR`, `SCHEDULE_MINUTE`.

## Running Tests

```bash
python -m pytest tests/ -v
```

84 tests covering: text utilities, keyword density, dash detection, duplicate detection, SEO validation, style validation, business management, DOCX generation, Google Sheets parsing, data models, and full pipeline mock runs.

## Troubleshooting

**"Could not resolve authentication method"**: Set `ANTHROPIC_API_KEY` in `.env` or use `--mock` for testing.

**Google Sheets auth errors**: Verify the service account JSON path and that the sheet is shared with the service account email.

**DOCX not generated**: Check `logs/` for detailed error logs. Each run creates a JSON log file.

**Keyword density too low/high**: The system attempts revision. If it fails after max attempts, the article is included with a QA warning.

**Em dash/en dash errors**: The system strips these automatically. If QA still fails, check the writer prompt.

## Cost Considerations

- Each article uses ~4-6 Claude API calls (topic selection shared across batch)
- 5 articles per business = ~25-30 API calls per business per run
- Uses cheaper models (Haiku) for validation where possible
- Caches business research and website content between articles
- Previous topic/keyword history prevents wasted research on duplicates

## Security

- API keys stored in `.env` (gitignored)
- Google credentials in `credentials/` (gitignored)
- No secrets in DOCX output or logs
- No arbitrary LLM-generated shell commands
- File operations restricted to configured directories
- All external URLs validated before use

## Known Limitations

- Web research depends on websites being accessible (some block bots)
- Keyword density is based on word count, not more sophisticated NLP
- Duplicate detection uses Jaccard similarity (semantic similarity would need embeddings)
- No real search volume data (marked "Not available" per design)
- Image concepts are text descriptions, not generated images
- Google Drive upload requires additional Drive API scope configuration

#!/usr/bin/env python
"""Lithuanian Shorts internal tool.

    python run.py serve         # paleisti web įrankį (rekomenduojama)
    python run.py scrape        # atnaujinti filmų archyvą iš svetainės
    python run.py programme -k "šeima,vaikystė" --year-from 2018
    python run.py report --director "Vardas Pavardė"

Duomenys saugomi Supabase duomenų bazėje. Prieš paleidžiant reikia .env failo
su SUPABASE_URL, SUPABASE_SERVICE_KEY ir FLASK_SECRET_KEY (žr. .env.example).
"""
import sys

from dotenv import load_dotenv

# Local runs read the keys from .env; on Vercel they come from the environment.
load_dotenv()

from ls_tool.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

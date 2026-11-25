"""Synthetic CV and job pairs used by the cost and model-comparison evals.

Do not put real personal data here. Each sample is a CV and a job description.
"""

SAMPLES = [
    {
        "name": "python_developer",
        "cv": (
            "דנה לוי\n"
            "ניסיון\n"
            "- מפתחת Python בחברת תוכנה, 3 שנים\n"
            "- כתיבת שירותי API עם FastAPI\n"
            "- עבודה עם מסדי נתונים PostgreSQL\n"
            "השכלה\n"
            "- B.Sc. במדעי המחשב, אוניברסיטת תל אביב\n"
        ),
        "job": "מפתח/ת Python לצוות backend, ניסיון ב-FastAPI ו-SQL, משרה מלאה.",
    },
    {
        "name": "data_analyst",
        "cv": (
            "יוסי כהן\n"
            "ניסיון\n"
            "- אנליסט נתונים בחברת מסחר, שנתיים\n"
            "- הכנת דוחות ב-Excel ובניית לוחות בקרה\n"
            "- שאילתות SQL לניתוח מכירות\n"
            "השכלה\n"
            "- תואר ראשון בסטטיסטיקה\n"
        ),
        "job": "אנליסט/ית נתונים, ניסיון ב-SQL ובהצגת נתונים, עבודה מול צוות מכירות.",
    },
]
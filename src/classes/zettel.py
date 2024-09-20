from pathlib import Path
from typing import List

from pydantic import BaseModel


class CiteField(BaseModel):
    bibkey: str = ""
    page: int = -1


class DateField(BaseModel):
    year: int = -1
    era: str = "AD"


class Zettel(BaseModel):
    title: str = ""
    bibkey: str = ""
    bibtex: str = ""
    ris: str = ""
    inline: str = ""
    url: str = ""
    summary: str = ""
    comment: str = ""
    note: str = ""
    tags: List[str] = [""]
    mentions: List[str] = [""]
    cite: CiteField = CiteField()
    dates: List[DateField] = [DateField()]
    filename: str = Path().resolve(strict=True).__str__()
    document: str = ""

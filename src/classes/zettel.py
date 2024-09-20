from pathlib import Path
from typing import List

import yaml


class CiteField:
    def __init__(self, bibkey: str = "", page: int = -1) -> None:
        self.bibkey: str = bibkey
        self.page: int = page


class DateField:
    def __init__(self, year: int = -1, era: str = "AD") -> None:
        self.year: int = year
        self.era: str = era


class Zettel:
    def __init__(
        self,
        title: str = "",
        bibkey: str = "",
        bibtex: str = "",
        ris: str = "",
        inline: str = "",
        url: str = "",
        summary: str = "",
        comment: str = "",
        note: str = "",
        tags: List[str] = [""],
        mentions: List[str] = [""],
        cite: CiteField = CiteField(),
        dates: List[DateField] = [DateField()],
        filename: Path = Path(),
        document: str = "",
    ) -> None:
        self.title: str = title
        self.bibkey: str = bibkey
        self.bibtex: str = bibtex
        self.ris: str = ris
        self.inline: str = inline
        self.url: str = url
        self.summary: str = summary
        self.comment: str = comment
        self.note: str = note
        self.filename: Path = filename.resolve(strict=True)
        self.document: str = document
        self.tags: List[str] = tags
        self.mentions: List[str] = mentions
        self.cite: CiteField = cite
        self.dates: List[DateField] = dates

    def toYAML(self) -> str:
        data: dict[str, str] = {
            "title": self.title,
            "bibkey": self.bibkey,
            "bibtex": self.bibtex,
            "ris": self.ris,
            "inline": self.inline,
            "url": self.url,
            "summary": self.summary,
            "comment": self.comment,
            "note": self.note,
            "document": self.document,
        }

        return yaml.safe_dump(data=data, indent=4)

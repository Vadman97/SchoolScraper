import dataclasses
from enum import Enum
from html.parser import HTMLParser

import requests

subject_regex = '.*label="(.+)" value="(.*)".*'
agency_regex = '.*value="(.+?)".*>(.+?)</option>'


class Level(Enum):
    STATE = "State"
    COUNTY = "County"
    DISTRICT = "District"
    SCHOOL = "School"
    SELPA = "SELPA"
    OTHER = "Other Choices"


@dataclasses.dataclass
class Subject:
    label: str
    value: str


@dataclasses.dataclass
class Report:
    name: str
    value: str


@dataclasses.dataclass
class Agency:
    search: str
    name: str
    value: str


SUBJECTS = [
    # TODO(vkorolik) needs unique support
    # Subject(label="California School Dashboard", value="CaDshbrd"),
    # TODO(vkorolik) needs unique support
    # Subject(label="Dashboard Additional Reports and Data", value="CaModel"),
    # TODO(vkorolik) needs unique support
    # Subject(label="CAASPP Test Results", value="CAASPP"),
    # Subject(label="English Language Proficiency Assessments for CA (ELPAC)", value="ELPAC"),
    Subject(label="Physical Fitness Test (PFT)", value="FitTest"),
    Subject(label="Annual Enrollment Data", value="Enrollment"),
    Subject(label="English Learner Data", value="LC"),
    Subject(label="Foster Student Data", value="Foster"),
    Subject(label="Special Education Data", value="SpecEd"),
    Subject(label="Four-Year Cohort Graduation Rates &amp; Outcomes", value="Coh"),
    Subject(label="Five-Year Cohort Graduation Rates", value="Coh5"),
    Subject(label="One-Year Graduation Data", value="Graduates"),
    Subject(label="One-Year Dropout Data", value="Dropouts"),
    Subject(label="College-Going Rates", value="CGR"),
    Subject(label="Suspension and Expulsion Data", value="Expulsion"),
    Subject(label="Absenteeism Data", value="Attendance"),
    Subject(label="Stability Rates", value="STB"),
    Subject(label="Staff Assignment Data", value="TCH"),
    Subject(label="Staff Demographic Data", value="Paif"),
    Subject(label="Estimated Teacher Hires", value="Hires"),
    Subject(label="Course Enrollment &amp; Class Size Data", value="Course"),
    Subject(label="CA Healthy Kids Survey", value="HKids"),
    Subject(
        label="CA School Staff Survey (formerly CA School Climate Survey)", value="CSCS"
    ),
    Subject(label="CA School Climate Report Card", value="CSCR"),
    Subject(label="Free and Reduced Price Meals", value="FRPM"),
    Subject(label="Create Your Own Report", value="Profile"),
]

REPORTS = [
    Report(name="Five-Year Cohort Graduation Rate", value="Coh5YrRate"),
    Report(name="Five-Year Cohort Outcome", value="Coh5YrOutcome"),
    Report(
        name="Five-Year and Four-Year Cohort Graduation Rate Comparison",
        value="Coh5yr4YrComp",
    ),
]


class DataRow(dict):
    pass


class YearParser(HTMLParser):
    start: int
    end: int

    def __init__(self):
        super().__init__()
        self.data: str | None = None
        self.type: str | None = None
        self.start = 9999
        self.end = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'select':
            for attr in attrs:
                if attr[0] == 'name':
                    self.type = attr[1]
        elif tag == 'option' and self.type == 'rYear':
            for attr in attrs:
                if attr[0] == 'value':
                    self.start = min(self.start, int(attr[1].split('-')[0]))
                    self.end = max(self.end, self.start + 1)

    def handle_data(self, data):
        self.data = data


class DataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.data: str | None = None

        self.columns: list[str] = []
        self.col_idx: int = 0

        self.rows: list[DataRow] = []
        self.current_row: DataRow | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr" and self.columns:
            self.col_idx = 0
            self.current_row = DataRow()
            self.data = None

    def handle_endtag(self, tag):
        if tag == "tr" and self.columns and self.current_row is not None:
            self.rows.append(self.current_row)
            self.col_idx = 0
            self.current_row = None
        elif tag == "th":
            self.columns.append(self.data)
            self.col_idx += 1
            self.data = None
        elif tag == "td" and self.current_row is not None:
            self.current_row[self.columns[self.col_idx]] = self.data
            self.col_idx += 1
            self.data = None

    def handle_data(self, data):
        self.data = data


def scrape(query: str, level: Level, subject: Subject):
    # gives allowed years for this level and subject
    r = requests.get(
        f"https://dq.cde.ca.gov/dataquest/page2.asp",
        params={"level": level.value, "subject": subject.value, "submit1": "Submit"},
    )
    assert r.ok

    year_parser = YearParser()
    year_parser.feed(r.text)

    for year_start in range(year_parser.start, year_parser.end):
        year_end2_digit = year_start - 1999
        r = requests.get(
            f"https://dq.cde.ca.gov/dataquest/SearchName.asp",
            params={
                "rbTimeFrame": "oneyear",
                "rYear": f"{year_start}-{year_end2_digit}",
                "cName": query,
                "Topic": subject.value,
                "Level": level.value,
                "submit1": "Submit",
            },
        )
        # TODO(vkorolik) gives report and agency options
        assert r.ok

        data = collect_data(Agency(
            search="North High",
            name="North^High--Torrance^Unifie--1965060-1936277",
            value="North High&nbsp;--&nbsp;Torrance Unifie&nbsp;--&nbsp;1965060-1936277",
        ), subject, REPORTS[0], year_start)
        print(data)


def collect_data(agency: Agency, subject: Subject, report: Report, year_start: int) -> list[DataRow]:
    year_end2_digit = year_start - 1999

    # gives the actual data page, from which we extract the data table
    r = requests.get(
        f"https://dq.cde.ca.gov/dataquest/SchGrad.asp",
        params={
            "cSelect": agency.value,
            "cChoice": report.value,
            "cYear": f"{year_start}-{year_end2_digit}",
            "cLevel": "School",
            "cTopic": subject.value,
            "myTimeFrame": "S",
            "submit1": "Submit",
        },
    )
    assert r.ok

    parser = DataParser()
    parser.feed(r.text)
    return parser.rows


def main():
    for subject in SUBJECTS:
        scrape('Coachella Valley', Level.SCHOOL, subject)


if __name__ == "__main__":
    main()

#
# zettel.py - A checker for Zettels
#

import argparse
import readline  # for input()
import sys

import frontmatter  # to accommodate Markdown with YAML frontmatter
import yaml

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader, Dumper

import json
import os
import os.path
import shutil
from time import strftime

# Recursive descent parsing of Zettel dictionary format.

ZettelStringFields = [
    "title",
    "bibkey",
    "bibtex",
    "ris",
    "inline",
    "url",
    "summary",
    "comment",
    "note",
]
ZettelListFields = ["tags", "mentions"]
ZettelStructuredFields = ["cite", "dates"]
ZettelExtraFields = ["filename", "document"]
ZettelFieldsOrdered = (
    ZettelStringFields + ZettelListFields + ZettelStructuredFields + ZettelExtraFields
)
ZettelFields = set(ZettelFieldsOrdered)
CitationFields = set(["bibkey", "page"])
DatesFields = set(["year", "era"])

ZettelMarkdownExtensions = [".text", ".txt", ".md", ".markdown"]


class ParseError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


def typename(value):
    return type(value).__name__


def parse_zettel(doc):
    if not isinstance(doc, dict):
        raise ParseError(
            "Zettels require key/value mappings at top-level. Found %s" % typename(doc)
        )

    parse_check_zettel_field_names(doc)

    # These fields are all optional but, if present, must be strings
    parse_string_field(doc, "title")
    parse_string_field(doc, "bibkey")
    parse_string_field(doc, "bibtex")
    parse_string_field(doc, "ris")
    parse_string_field(doc, "inline")
    parse_string_field(doc, "url")
    parse_string_field(doc, "summary")
    parse_string_field(doc, "comment")
    parse_string_field(doc, "note")
    parse_string_field(doc, "document")

    # These fields are all optional but, if present, must be list of strings

    parse_list_of_string_field(doc, "tags")
    parse_list_of_string_field(doc, "mentions")

    parse_citation(doc, "cite")
    parse_dates(doc, "dates")

    # TODO: Check for extraneous fields in all cases


def parse_check_zettel_field_names(doc):
    check_field_names(doc, ZettelFields, "Zettel")


def parse_check_citation_field_names(doc):
    check_field_names(doc, CitationFields, "Citation")


def parse_check_dates_field_names(doc):
    check_field_names(doc, DatesFields, "Dates")


def check_field_names(doc, name_set, label):
    for key in doc.keys():
        if key not in name_set:
            raise ParseError("Invalid field %s found in %s" % (key, label))


def parse_string_field(doc, field, required=False):
    value = doc.get(field, None)
    if value == None:
        if required:
            raise ParseError(
                "Field %s requires a string but found %s of type %s"
                % (field, value, typename(value))
            )
        # This extra check is needed to handle situation where a YAML field is
        # present but is null. We cannot allow it.
        if field in doc:
            raise ParseError("Field %s may not be (YAML) null" % field)
        return
    if not isinstance(value, str):
        raise ParseError(
            "Field %s must be a string or not present at all - found value %s of type %s"
            % (field, value, typename(value))
        )
    # if len(value) == 0:
    #    raise ParseError("Field %s is an empty string. Not permitted." % field)


# TODO: There is a possible bug in list of string that allows a field to be defined as YAML none.


def parse_list_of_string_field(doc, field, required=False):
    value = doc.get(field, None)
    if value == None:
        if required:
            raise ParseError("Field %s requires a list of strings" % field)
        # This extra check is needed to handle situation where a YAML field is
        # present but is null. We cannot allow it.
        if field in doc:
            raise ParseError("Field %s may not be (YAML) null" % field)
        return
    if not isinstance(value, (list, tuple)):
        raise ParseError(
            "Field %s must be a list or not present at all - found value %s of type %s"
            % (field, value, typename(value))
        )

    # Make a dictionary of the list items for checking purposes only
    # That is, treat the list like a dictionary. Will simplify with comprehension magic later
    doc2 = {}
    pos = 0
    for item in value:
        doc2["%s(%d)" % (field, pos)] = item
        pos = pos + 1
    for key in doc2.keys():
        parse_string_field(doc2, key, True)


def parse_citation(doc, field):
    value = doc.get(field, None)
    if value == None:
        return
    if not isinstance(value, dict):
        raise ParseError("%s must be a nested (citation) dictoinary" % field)
    parse_check_citation_field_names(value)
    parse_string_field(value, "bibkey", True)
    parse_string_field(value, "page")


def parse_dates(doc, field):
    value = doc.get(field, None)
    if value == None:
        return
    if not isinstance(value, dict):
        raise ParseError("%s must be a nested (dates) dictionary" % field)
    parse_check_dates_field_names(value)
    parse_string_field(value, "year", True)
    parse_string_field(value, "era")


# This is to support formatting of resulting YAML (after modification of the underlying dictionary)


# Credit to StackOverflow for helping figure out how to format YAML
# multiline strings properly (when emitting YAML representation of Zettel)

from collections import OrderedDict


class quoted(str):
    pass


class literal(str):
    pass


def quoted_presenter(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


# Note: Only use multiline syntax when there are actually multiple lines.


def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def ordered_dict_presenter(dumper, data):
    return dumper.represent_dict(data.items())


class ZettelBadKey(Exception):
    def __init__(self, name):
        self.name = name


class ZettelStringRequired(Exception):
    def __init__(self, value):
        self.value = value


def get_argparse():
    parser = argparse.ArgumentParser()

    # note is being deprecated in future releases to give users time to migrate away from it

    for field in ZettelFieldsOrdered:
        parser.add_argument(
            "--delete-%s" % field,
            action="store_true",
            help="delete field %s" % field,
            default=False,
        )

    for field in ZettelStringFields + ZettelExtraFields:  # allow for filename, doc
        parser.add_argument(
            "--set-%s" % field, help="set the value of field %s" % field
        )
        parser.add_argument(
            "--load-%s" % field, help="load field %s from filename" % field
        )

    for field in ZettelListFields:
        parser.add_argument(
            "--reset-%s" % field,
            action="store_true",
            help="reset list field %s" % field,
            default=False,
        )
        parser.add_argument(
            "--remove-entries-in-%s" % field,
            nargs=2,
            metavar=("FASS ENTRY", "LIST ENTRY"),
            type=str,
            help="delete comma-separated LIST ENTRY positions from FASS ENTRY",
        )
        parser.add_argument(
            "--append-%s" % field, nargs="+", help="add value to list field %s" % field
        )

    parser.add_argument(
        "--set-cite",
        nargs="+",
        type=str,
        metavar=("BIBKEY", "PAGES"),
        help="set citation BIBKEY [ PAGE* ] - leave blank to override existing BIBKEY",
    )

    parser.add_argument(
        "--set-dates",
        nargs="+",
        type=str,
        metavar=("YEAR", "ERA"),
        help="set dates; YEAR required - ERA is optional (extra arguments beyond the 2nd are ignored but allowed",
    )

    for field in ZettelFieldsOrdered:
        parser.add_argument(
            "--prompt-%s" % field,
            action="store_true",
            help="prompt for input of %s" % field,
            default=False,
        )

    parser.add_argument(
        "--file", help="Zettel file (.yaml) to process (or check syntax)"
    )

    parser.add_argument("--save", help="Write output to specified file.")

    parser.add_argument(
        "--in-place",
        action="store_true",
        default=False,
        help="overwrite original file specified by --file",
    )

    parser.add_argument(
        "--backup-id", help="backup suffix for original filename", default="orig"
    )

    parser.add_argument(
        "--name", nargs="+", help="order of components, e.g. id, or timestamp"
    )
    parser.add_argument(
        "--name-dir",
        type=str,
        help="folder where to write file generated by --name (will NOT be created, if it does not exist)",
        default=".",
    )
    parser.add_argument("--id", help="human-understandable id to include in filename")
    parser.add_argument(
        "--digits", type=int, help="digits in counter (default=4)", default=4
    )

    parser.add_argument(
        "--separator",
        type=str,
        help="separate components with delimiter (default is '-')",
        default="-",
    )
    parser.add_argument(
        "--counter", type=str, help="counter name (defaults to --id if present) "
    )
    parser.add_argument(
        "--counter-path",
        type=str,
        help="counter filename/path to filename",
        default=".counter.dat",
    )

    parser.add_argument(
        "--restrict-output-fields",
        nargs="+",
        help="restrict output fields (list of Zettel field names)",
        default=ZettelFieldsOrdered,
    )

    # deprecated
    parser.add_argument(
        "--omit-markdown-header",
        action="store_true",
        default=False,
        help="add markdown header when writing Markdown for each YAML field",
    )

    return parser


def flatten(item):
    if item == None:
        return [""]
    elif isinstance(item, dict):
        return flatten([":".join([k, item[k]]) for k in item])
    elif not isinstance(item, (tuple, list)):
        return [str(item)]

    if len(item) == 0:
        return item
    else:
        return flatten(item[0]) + flatten(item[1:])


def prompt(field):
    print("Enter text for %s. ctrl-d to end." % field)
    lines = []
    while True:
        try:
            line = input("%s> " % field)
            lines.append(line)
        except EOFError:
            print()
            break
    return lines


class Zettel(object):
    def __init__(self, data={}):
        self.zettel = data
        parse_zettel(self.zettel)

    def set_field(self, name, value):
        self.zettel[name] = value
        parse_zettel(self.zettel)

    def delete_field(self, name):
        try:
            del self.zettel[name]
        except:
            pass
        parse_zettel(self.zettel)

    def reset_list_field(self, name):
        self.zettel[name] = []
        parse_zettel(self.zettel)

    def delete_list_field_entries(self, name, positions):
        if name not in self.zettel:
            return
        positions.sort(reverse=True)
        for position in positions:
            del self.zettel[name][position]
        if len(self.zettel[name]) == 0:
            del self.zettel[name]

    def append_list_field(self, name, value):
        self.zettel[name] = self.zettel.get(name, [])
        tag_set = set(self.zettel[name])
        if not value in tag_set:
            self.zettel[name].append(value)
            parse_zettel(self.zettel)

    def get_list_field(self, name):
        return self.zettel.get(name, [])

    def set_citation(self, bibkey, page=None):
        citation = {"bibkey": bibkey}
        if page != None:
            citation["page"] = page
        self.zettel["cite"] = citation
        parse_zettel(self.zettel)

    def has_citation(self):
        return "cite" in self.zettel

    def set_cite_bibkey(self, bibkey):
        if len(bibkey) == 0:
            return
        if self.has_citation():
            self.zettel["cite"]["bibkey"] = bibkey
        parse_zettel(self.zettel)

    def set_cite_page(self, page):
        if len(page) == 0:
            return
        if self.has_citation():
            self.zettel["cite"]["page"] = page
        parse_zettel(self.zettel)

    def has_dates(self):
        return "dates" in self.zettel

    def set_dates_year(self, year):
        if len(year) == 0:
            return
        if self.has_dates():
            self.zettel["dates"]["year"] = year
        parse_zettel(self.zettel)

    def set_dates_era(self, era):
        if len(era) == 0:
            return
        if self.has_dates():
            self.zettel["dates"]["era"] = era
        parse_zettel(self.zettel)

    def set_dates(self, year, era=None):
        dates = {"year": year}
        if era != None:
            dates["era"] = era
        self.zettel["dates"] = dates
        parse_zettel(self.zettel)

    def load_field(self, name, filename):
        text = []
        with open(filename, "r") as infile:
            text = infile.readlines()
        text = "".join(text)
        text = text.strip()
        self.set_field(name, text)
        parse_zettel(self.zettel)

    def get_yaml(self, restrict_to_fields=ZettelFieldsOrdered):
        yaml.add_representer(quoted, quoted_presenter)
        yaml.add_representer(literal, str_presenter)
        yaml.add_representer(OrderedDict, ordered_dict_presenter)
        parse_zettel(self.zettel)
        yaml_zettel = OrderedDict()
        for key in ZettelFieldsOrdered:
            if key not in self.zettel:
                continue
            if key not in restrict_to_fields:
                continue
            if key in ZettelStringFields:
                yaml_zettel[key] = literal(self.zettel[key])
            elif key != "document":  # Only field not allowed is Markdown document
                try:
                    yaml_zettel[key] = self.zettel[key].copy()
                except:
                    print("Warning: Cannot copy %s" % key)
        if len(yaml_zettel) > 0:
            return yaml.dump(yaml_zettel, default_flow_style=False)
        else:
            return ""

    def get_document(self):
        return self.zettel.get("document", "")

    def get_filename(self):
        return self.zettel.get("filename", "")

    # Unlikely we need this code anymore.
    # def get_text(self, omit_markdown_header, restrict_to_fields=ZettelFieldsOrdered):
    #     text = []
    #     parse_zettel(self.zettel)
    #     for key in ZettelFieldsOrdered:
    #         if key not in self.zettel:
    #             continue
    #         if key not in restrict_to_fields:
    #             continue
    #         if not omit_markdown_header:
    #            text.append(markdown_h1(key))
    #         if key in ZettelStringFields:
    #             text.append(self.zettel[key].strip())
    #         elif key in ZettelListFields:
    #             for item in self.zettel[key]:
    #                 text.append(markdown_listitem(item))
    #         else:
    #             text.append(self.get_yaml([key]))
    #         text.append("\n")
    #     return "\n".join(text)

    def get_yaml_subset(self, fields=[]):
        z = Zettel({})
        for field in fields:
            z.zettel[field] = self.zettel[field].copy()

    def get_indexed_representation(self):
        parse_zettel(self.zettel)
        return {key: ",".join(flatten(self.zettel[key])) for key in self.zettel}


# deprecated
# def markdown_h1(text):
#     return "\n".join([text, len(text) * "="]) + "\n"
# deprecated
# def markdown_listitem(text):
#    return "- %s" % text.strip().replace("\n", "").replace("\r", "")


class ZettelLoaderError(Exception):
    def __init__(self, message):
        self.message = message


def load_pure_yaml(filepath):
    # TODO: Consider using the frontmatter to load the YAML and do all error reporting.
    # print("Importing YAML: %s" % filepath)
    ydoc = {}
    document = ""
    with open(filepath) as infile:
        try:
            text = infile.read()
        except:
            print("- Warning: I/O error on %s; is doc UTF-8" % filepath)
            return (ydoc, document)
        try:
            ydocs = yaml.load_all(text, Loader=Loader)
        except:
            print(
                "- Warning: Cannot load YAML from %s; consider running YAML linter"
                % filepath
            )
            return (ydoc, document)

        try:
            ydoc = next(ydocs)
        except:
            print("- Warning: Cannot load first YAML document from %s" % filepath)
            return (ydoc, document)
    return (ydoc, document)


def load_markdown_with_frontmatter(filepath):
    # print("Importing Markdown with Frontmatter: %s" % filepath)
    post = frontmatter.load(filepath)
    return (post.metadata, post.content)


class ZettelLoader(object):
    def __init__(self, infile):
        # developer note: When we developed this code, we were thinking about a "fass" of zettels.
        # Now we just have individual zettels.
        if infile.endswith(".yaml"):
            self.ydocs = [load_pure_yaml(infile)]
        elif infile.endswith(".md"):
            self.ydocs = [load_markdown_with_frontmatter(infile)]
        else:
            self.ydocs = []

    def getZettels(self):
        for yaml_document in self.ydocs:
            (ydoc, document) = yaml_document
            ydoc["document"] = document
            if isinstance(ydoc, dict):
                yield Zettel(ydoc)
            else:
                yield Zettel({})


def main():
    parser = get_argparse()
    args = parser.parse_args()
    argsd = vars(args)
    argsd["timestamp"] = True
    z_generator = gen_new_zettels(args)

    try:
        first_zettel = next(z_generator)
    except ParseError as error:
        print(error)

    filename = None
    if args.in_place:
        if not args.file:
            print("--in-place requires --file")
            sys.exit(1)
        filename = args.file
        filename_parts = os.path.splitext(filename)
        if filename_parts[1] not in [".yaml", ".md"]:
            print("Input file not .yaml/.md: %s" % filename)
            sys.exit(1)
        backup_filename = ".".join([filename, args.backup_id])
        shutil.copyfile(filename, backup_filename)
        outfile = open(args.file, "w")
    elif args.save:
        filename = args.save
        if args.file == args.save:
            print(
                "Use --in-place instead of --save if you want to replace input file (specified with --file)"
            )
            sys.exit(1)
        if os.path.exists(filename):
            backup_filename = ".".join([filename, args.backup_id])
            shutil.copyfile(filename, backup_filename)
        outfile = open(args.save, "w")
    elif args.name:
        name_components = {}
        name_dir = args.name_dir
        if not os.path.exists(name_dir):
            print(
                "Destination directory specified (--name-dir %s) does not exist. Will not write file."
            )
            sys.exit(1)
        for arg in args.name:
            if arg not in ["id", "timestamp", "counter"]:
                print("--name may only use id, counter, and timestamp (%s found)" % arg)
                sys.exit(1)
            if not argsd.get(arg, None) != None:
                print("--name %s requires --%s" % (args.name, arg))
                print(argsd)
                sys.exit(1)
        if args.id != None:
            name_components["id"] = args.id
        digits = args.digits

        # --counter and --id can be specified separately
        # If omitted, --counter takes on --id
        # If both are omitted, then we are not using counters in the generated names.
        counter_name = args.counter
        if not args.counter:
            counter_name = args.id

        if counter_name != None:
            seq = get_count(args.counter_path, counter_name)
            seq_text = str(seq)
            digits = max(len(seq_text), digits)
            pad_text = "0" * (digits - len(seq_text))
            name_components["counter"] = pad_text + seq_text

        name_components["timestamp"] = strftime("%Y%m%d%H%M%S")

        name_template = (
            args.separator.join(["%%(%s)s" % name for name in args.name]) + ".md"
        )
        name_template = "/".join([name_dir, name_template])
        filename = name_template % name_components
        if os.path.exists(filename):
            backup_filename = ".".join([filename, args.backup_id])
            shutil.copyfile(filename, backup_filename)
        outfile = open(filename, "w")
    else:
        outfile = sys.stdout

    if filename:
        (basename, extension) = os.path.splitext(filename)
    else:
        extension = ".yaml"

    try:
        yaml_repr_stripped = first_zettel.get_yaml(args.restrict_output_fields).rstrip()
        document = first_zettel.get_document()
        if len(yaml_repr_stripped) > 0:
            outfile.write(
                "\n".join(["---", yaml_repr_stripped, "---", document.rstrip()]) + "\n"
            )
        else:
            doc_stripped = document.rstrip()
            if len(doc_stripped) > 0:
                outfile.write(doc_stripped + "\n")
    except ParseError as error:
        print(error)


def gen_id():
    id = 0
    while True:
        yield id
        id = id + 1


def gen_new_zettels(args):
    vargs = vars(args)
    id_gen = gen_id()
    if args.file:
        loader = ZettelLoader(args.file)
        last_z = None
        for z in loader.getZettels():
            last_z = process_zettel_command_line_options(z, vargs, next(id_gen))
            yield last_z
        if not last_z:
            yield process_zettel_command_line_options(Zettel(), vargs, next(id_gen))
    else:
        yield process_zettel_command_line_options(Zettel(), vargs, next(id_gen))


def process_zettel_command_line_options(z, vargs, id):
    # --reset-*, --delete-*, and --remove_entries_in-* are evaluated first
    for arg in vargs:
        if not vargs[arg]:
            continue

        if arg.startswith("reset_"):
            reset_what = arg[len("reset_") :]
            z.reset_list_field(reset_what)

        if arg.startswith("delete_"):
            delete_what = arg[len("delete_") :]
            z.delete_field(delete_what)

        if arg.startswith("remove_entries_in_"):
            delete_what = arg[len("remove_entries_in_") :]
            try:
                (zettel_id, list_entries) = vargs[arg][:2]
                zettel_id = int(zettel_id)
                list_entries = [int(pos) for pos in list_entries.split(",")]
            except:
                print(
                    "Non-integer zettel ID or list position found in %s. Aborting."
                    % arg
                )
                sys.exit(1)
            if id == zettel_id:
                z.delete_list_field_entries(delete_what, list_entries)

    for arg in vargs:
        if not vargs[arg]:
            continue
        if arg == "set_cite":
            cite_info = vargs[arg]
            bibkey = cite_info[0]
            pages = ",".join(cite_info[1:])

            if z.has_citation():
                z.set_cite_bibkey(bibkey)
                z.set_cite_page(pages)
            else:
                z.set_citation(bibkey, pages)

        elif arg == "set_dates":
            date_info = vargs[arg]
            year = date_info[0]
            era = ",".join(date_info[1:])
            if z.has_dates():
                z.set_dates_year(year)
                z.set_dates_era(era)
            else:
                z.set_dates(year, era)

        elif arg.startswith("set_"):
            set_what = arg[len("set_") :]
            value = vargs[arg].replace(r"\n", "\n")
            z.set_field(set_what, value)

        elif arg.startswith("prompt_"):
            prompt_field = arg[len("prompt_") :]
            lines = prompt(prompt_field)
            if prompt_field in ZettelStringFields:
                z.set_field(prompt_field, "\n".join(lines))
            elif prompt_field in ZettelExtraFields:
                z.set_field(prompt_field, "\n".join(lines))
            elif prompt_field in ZettelListFields:
                for line in lines:
                    z.append_list_field(prompt_field, line)
            elif prompt_field == "dates":
                if len(lines) > 0:
                    try:
                        z.set_dates(lines[0], lines[1])
                    except:
                        z.set_dates(lines[0])
            elif prompt_field == "cite":
                if len(lines) > 0:
                    try:
                        z.set_citation(lines[0], lines[1])
                    except:
                        z.set_citation(lines[0])

        if arg.startswith("append_"):
            append_what = arg[len("append_") :]
            for text in vargs[arg]:
                z.append_list_field(append_what, text)

        if arg.startswith("load_"):
            load_what = arg[len("load_") :]
            z.load_field(load_what, vargs[arg])
    return z


def get_count(counter_path, counter_name):
    # Create counter db if not present.
    if not os.path.exists(counter_path):
        with open(counter_path, "w") as dbfile:
            json.dump({}, dbfile)

    # Read count from counter. If non-existent, start at 0.
    with open(counter_path, "r") as dbfile:
        db = json.load(dbfile)
        count = db.get(counter_name, -1) + 1

    # save count for next invocation
    with open(counter_path, "w") as dbfile:
        db[counter_name] = count
        json.dump(db, dbfile)
    return count


def dict_as_yaml(data):
    yaml.add_representer(quoted, quoted_presenter)
    yaml.add_representer(literal, str_presenter)
    yaml.add_representer(OrderedDict, ordered_dict_presenter)
    presented_data = OrderedDict()
    for key in data:
        if key in ZettelStringFields:
            presented_data[key] = literal(data[key])
        else:
            presented_data[key] = data[key]
    return yaml.dump(presented_data, default_flow_style=False, Dumper=Dumper)


if __name__ == "__main__":
    main()

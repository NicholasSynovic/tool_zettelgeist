from src.classes.zettel import Zettel


def main() -> None:
    z: Zettel = Zettel()
    print(z.toYAML())


if __name__ == "__main__":
    main()

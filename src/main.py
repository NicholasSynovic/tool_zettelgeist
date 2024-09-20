import yaml

from src.classes.zettel import Zettel


def main() -> None:
    z: Zettel = Zettel()
    print(z.model_dump())
    print(yaml.safe_dump(data=z.model_dump()))


if __name__ == "__main__":
    main()

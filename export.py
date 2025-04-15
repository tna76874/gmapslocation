#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import yaml
import os
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, create_engine, Session, select
from locationsharinglib import Service
import argparse
from urllib.parse import quote
import requests


class PersonModel(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: str = Field(default=None, primary_key=True)
    full_name: str
    nickname: Optional[str] = None
    latitude: float
    longitude: float
    timestamp: Optional[str] = None
    datetime: Optional[str] = None
    accuracy: Optional[float] = None
    address: Optional[str] = None
    country_code: Optional[str] = None
    charging: Optional[bool] = None
    battery_level: Optional[int] = None

    def __init__(self, **data):
        # Timestamp umwandeln, falls nötig
        raw_ts = data.get("datetime")
        if raw_ts is not None and not isinstance(raw_ts, str):
            try:
                data["datetime"] = datetime.fromtimestamp(float(raw_ts)/1000, tz=timezone.utc).isoformat()
            except (ValueError, TypeError):
                data["datetime"] = None  # fallback wenn ungültig

        super().__init__(**data)

        # ID aus Hash berechnen, falls nicht gesetzt
        if not self.id:
            self.id = self.compute_hash()

    def compute_hash(self) -> str:
        keys = [
            self.full_name, self.nickname, self.latitude, self.longitude,
            self.timestamp, self.accuracy, self.address, self.country_code,
            self.charging, self.battery_level
        ]
        values = [str(v) if v is not None else '' for v in keys]
        combined = "|".join(values)
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()


class UploadedModel(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    
    id: str = Field(
        primary_key=True,
        foreign_key="personmodel.id"
    )
    upload_datetime: datetime = Field(default_factory=datetime.utcnow)

def load_config():
    with open('./data/config.yml', 'r') as file:
        return yaml.safe_load(file)


def setup_database(config):
    DATABASE_PATH = os.path.abspath(config.get('db_path', './data/data.db'))
    db_directory = os.path.dirname(DATABASE_PATH)
    if not os.path.exists(db_directory):
        os.makedirs(db_directory)
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
    engine = create_engine(DATABASE_URL)
    SQLModel.metadata.create_all(engine, checkfirst=True)
    return engine


def create_person(person_data, engine):
    person = PersonModel(
        full_name=person_data['_full_name'],
        nickname=person_data['_nickname'],
        latitude=person_data['_latitude'],
        longitude=person_data['_longitude'],
        timestamp=person_data['_timestamp'],
        datetime=person_data['_timestamp'],
        accuracy=person_data['_accuracy'],
        address=person_data['_address'],
        country_code=person_data['_country_code'],
        charging=person_data['_charging'],
        battery_level=person_data['_battery_level']
    )
    
    with Session(engine) as session:
        # Prüfe, ob die ID bereits existiert
        existing = session.get(PersonModel, person.id)
        if existing:
            return existing

        session.add(person)
        session.commit()
        session.refresh(person)
        return person
    

def create_uploaded(person: PersonModel, engine):
    with Session(engine) as session:
        result = session.get(UploadedModel, person.id)
        
        if result is not None:
            # Eintrag existiert bereits, nichts tun oder bestehenden zurückgeben
            return result
    
        uploaded = UploadedModel(id=person.id)


        session.add(uploaded)
        session.commit()
        session.refresh(uploaded)
        return uploaded


def update_database(config):
    cookies_file = os.path.abspath(config.get('cookies_path', './data/cookies.txt'))
    google_email = config['email']
    service = Service(cookies_file=cookies_file, authenticating_account=google_email)
    engine = setup_database(config)

    for person_gpx in service.get_all_people():
        pass
        # print(f"Updating person: {person_gpx.full_name}")
        person = create_person(person_gpx.__dict__, engine)
        

def update_position(person: PersonModel, config: dict, engine) -> str:
    # Hole Host und KEY aus der Konfiguration
    host = config['phonetrack']['host']
    key = config['phonetrack']['key']

    # URL-kodiertes Full Name
    session_name = quote(person.full_name)

    # Die URL zusammenbauen
    url = (
        f"https://{host}/apps/phonetrack/logGet/{key}/{session_name}?"
        f"lat={person.latitude}&lon={person.longitude}&alt=0&acc={person.accuracy or 0}"
        f"&bat={person.battery_level or 0}&sat=0&speed=0&bearing=0&timestamp={person.timestamp}"
    )
    
    # Führe den GET-Request aus
    try:
        response = requests.get(url)
        response.raise_for_status()  # Wird eine Ausnahme auslösen, wenn der Statuscode 4xx/5xx ist

        # Wenn erfolgreich, speichern wir den Hash und das aktuelle datetime in der Uploaded-Tabelle
        create_uploaded(person, engine)
        return response.text  # Gibt die Antwort des Servers zurück (kann JSON oder HTML sein)
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Senden der Anfrage: {e}")
        return None

def main():
    # CLI-Argumente definieren
    parser = argparse.ArgumentParser(description="Update the database with location data.")
    parser.add_argument('--update', action='store_true', help="Update the database with new data.")

    args = parser.parse_args()

    if args.update:
        config = load_config()
        update_database(config)
        print("Database update complete.")
    else:
        print("No action specified. Use --update to update the database.")
        
def ensure_all_positions_uploaded(config: dict, engine):
    with Session(engine) as session:
        # Alle Person-IDs abrufen
        all_persons_stmt = select(PersonModel)
        all_persons = session.exec(all_persons_stmt).all()

        # Alle bereits hochgeladenen IDs abrufen
        uploaded_ids_stmt = select(UploadedModel.id)
        uploaded_ids = set(session.exec(uploaded_ids_stmt).all())

        # Alle Personen filtern, die noch nicht hochgeladen wurden
        not_uploaded = [p for p in all_persons if p.id not in uploaded_ids]

        results = []
        for person in not_uploaded:
            result = update_position(person, config, engine)
            results.append((person.id, result))
        
        return results  # Optional: gibt Liste der Ergebnisse zurück


if __name__ == "__main__":
    config = load_config()
    engine = setup_database(config)

    update_database(config)
    ensure_all_positions_uploaded(config, engine)
    

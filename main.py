import requests

import datetime
import os

import yaml
import json

import logging
from pprint import pprint
from tqdm import tqdm

# Initial setup. Reading configuration and initializing logging
with open("config.yaml") as c:
    config = yaml.full_load(c)

# Configuration
LOG_DIR = "./app/log/"
REPORTS_DIR = f"./app/reports/{datetime.datetime.now().date()}/"

VK_APP_ID = config["VK"]["APP_ID"]
VK_TOKEN = config["VK"]["ACCESS_TOKEN"]
YADISK_TOKEN = config["YADISK"]["ACCESS_TOKEN"]

# Making working directories
for directory in [LOG_DIR, REPORTS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Initializing logging
logging.basicConfig(level=logging.INFO, filename=f"{LOG_DIR}{datetime.datetime.now().date()}_log.txt",
                    filemode="a", format="%(asctime)s %(levelname)s %(message)s", encoding="UTF-8")
logging.info('-' * 80)
logging.info(f'LAUNCHING at {datetime.datetime.now()}')
logging.info('-' * 80)


# Defining client classes
class VKclient:
    """Defining a custom VK client to work with API requests.
    Contains an access token and a method for getting a specific photo album."""
    def __init__(self, access_token, user_id, version="5.154"):
        self.token = access_token
        self.id = user_id
        self.version = version
        self.params = {"access_token": self.token, "v": self.version}

    def get_album(self, album_id="profile"):
        """Takes a VK album_id string.
        Return a json version of a reply from VK server."""
        url = "https://api.vk.com/method/photos.get"
        params = {"owner_id": self.id,
                  "album_id": album_id,
                  "extended": 1}

        logging.info(f"User-{self.id}. Trying to get album '{album_id}'")
        response = requests.get(url, params={**self.params, **params})

        return response.json().get("response", {})


class YADISKclient:
    """Defining a custom YA Disk client to work with API requests.
    Contains an access token and a methods for creating a directory
    and uploading a single file from URL."""
    def __init__(self, access_token):
        self.token = access_token
        self.headers = {"Authorization": self.token}

    def make_dir(self, path):
        """Takes a string path to a directory to be created.
        Creates a directory and returns server's response"""
        url = "https://cloud-api.yandex.net/v1/disk/resources"
        params = {"path": path}

        logging.info(f"Creating a folder: {path}")
        response = requests.put(url, headers=self.headers, params=params)

        return response.json()

    def upload_url(self, path, url):
        """Takes a string uploading path and a URL to a file.
        Uploads given URL to a specified path on disk space
        and returns a server's response."""
        base_url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
        params = {"path": path,
                  "url": url}

        logging.info(f"Uploading: {path}")
        response = requests.post(base_url, headers=self.headers, params=params)

        return response.json()


# Defining custom functions needed for the script
def proccess_album(album, count=5):
    """Takes the body of a response from VK photos.get method and a number of images to be processed.
    Returns a formatted form of the given album."""
    result = []
    likes_set = set([])

    for idx, item in zip(range(count), album.get("items", [])):
        entry = {"url": item.get("sizes", [])[-1].get("url", ""),
                 "size": item.get("sizes", [])[-1].get("type", "")}
        likes = item.get("likes", {}).get("count", 0)

        if likes not in likes_set:
            entry["file_name"] = f'{likes}.jpg'
            likes_set.add(likes)
        else:
            entry["file_name"] = f'{likes}_{item.get("date", 0)}.jpg'

        result += [entry]

    return result


def backup_album(client, album, path):
    """Takes a YADISKclient instance, formatted album and a string path.
    Creates a directory for the specified path and uploads given photo album to the created directory."""
    logging.info(f"Backing up to {path}")
    make_dir = client.make_dir(path)
    report = []

    for item in tqdm(album):
        url = item.get("url", "")
        file_path = path + "/" + item.get("file_name", "")
        client.upload_url(file_path, url)
        report += [{"file_name": item.get("file_name", ""),
                    "size": item.get("size", "")}]
    logging.info(f"Finished")

    return {"report": report}


# Main script
if __name__ == "__main__":
    # Getting external parameters
    user_id = input("Enter VK User ID: ")
    album_id = input("Enter Album ID (default=profile): ") or "profile"
    count = int(input("Enter number of photos to back up (default=5): ") or "5")

    # Initializing clients
    client_vk = VKclient(VK_TOKEN, user_id)
    client_yd = YADISKclient(YADISK_TOKEN)

    # Backing up chosen album
    album = client_vk.get_album(album_id)
    album_procc = proccess_album(album, count)
    backup_dir = f'/backup_user-{user_id}_{datetime.datetime.now().date()}'
    print(f"Backing up")
    report = backup_album(client_yd, album_procc, backup_dir)

    # Generating a report
    fn = f"{''.join(str(datetime.datetime.now().time()).split(':'))}_user-{user_id}.json"
    report_path = REPORTS_DIR + fn
    with open(report_path, "w") as f:
        json.dump(report, f)

    logging.info(f"Report generated at {report_path}")
    print(f"Finished")
    pprint(report)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Imports from third party packages
import redis
import yaml


REFRESH_INTERVAL = 1  # seconds


class RedisUpdater(object):
    def __init__(self, api_url, secret):
        self.api_url = api_url
        self.params = {"secret": secret}
        self.redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

    def ctf_services(self):
        pass

    def ctf_services_status(self):
        pass

    def ctf_teams(self):
        pass

    def ctf_scores(self):
        pass

    def store_redis(self, key, value):
        pass


def main():
    config_file = "config.yml"
    fh = open(config_file)
    config = yaml.load(fh.read())
    fh.close()
    redis_updater = RedisUpdater(config["api_base_url"], config["api_secret"])
    methods_to_run = [member for member in dir(redis_updater) if
                      member.startswith("ctf_")]
    for method in methods_to_run:
        getattr(redis_updater, method)()


if __name__ == "__main__":
    main()

#!/usr/bin/env python

import os
from git import Repo


class GitAgent:
    def __init__(self):
        pass

    def print_info(self):
        repo = Repo.init(os.curdir)
        print("Currently on branch:", repo.active_branch, '[', repo.active_branch.is_valid(), ']')
        # print("Commits:")
        # for com in repo.iter_commits(max_count=5):
        #     print("\t", com.author, com.committed_date, com.message)


g = GitAgent()
g.print_info()

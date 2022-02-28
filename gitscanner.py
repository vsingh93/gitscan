#! /usr/bin/python3

import json
import boto3
import requests
import os
import hvac
import datetime
import pandas as pd

print (f"\n\n\n{'*'*50}\nGIT SECRET SCANNING USING GITLEAKS\n{'*'*50}\n\n\n")

slack_channel = '#test-aws-channel'

def get_variables():
    ssm = boto3.client('ssm',region_name='ap-south-1')
    response = ssm.get_parameters(Names=['gh_token','gh_uname','slack_token'],WithDecryption=True)
    github_token = response['Parameters'][0]['Value']
    slack_token = response['Parameters'][2]['Value']
    gh_uname = response['Parameters'][1]['Value']
    fetch_repos(github_token,slack_token,gh_uname)

def merge_files(all_files,sl_token):
    combined_csv = pd.concat([pd.read_csv(f) for f in all_files ])
    combined_csv.to_csv( "combined_csv.csv", index=False, encoding='utf-8-sig')
    merged_data = open("combined_csv.csv","r")
    post_file_to_slack("Merged File",'',merged_data,sl_token)
    
def post_file_to_slack(text, file_name, file_bytes, slack_token, file_type=None, title=None):
    return requests.post(
      'https://slack.com/api/files.upload', 
      {
        'token': slack_token,
        'filename': file_name,
        'channels': slack_channel,
        'filetype': file_type,
        'initial_comment': text,
        'title': title
      },
      files = { 'file': file_bytes }).json()

def post_message_to_slack(text, slack_token, blocks = None):
    return requests.post('https://slack.com/api/chat.postMessage', {
        'token': slack_token,
        'channel': slack_channel,
        'text': text,
        'blocks': json.dumps(blocks) if blocks else None
    })

def fetch_repos(gh_token,sl_token,gh_uname):
    msg = "GIT SECRET SCANNING INITIATED ON {}".format(datetime.datetime.now())
    post_message_to_slack(msg,sl_token)
    url = "https://api.github.com/orgs/grofers/repos"
    headers = {"Accept":"application/vnd.github.v3+json", "Authorization":"token " + gh_token}
    repo_list = []
    for i in range (1,100):
        payload = {'type':'all','per_page':5000,'page':i}
        try:
            r =requests.get(url, headers=headers, params=payload)
            print (f"\nConnection Successfull !!! Fetching page {i}. .\n")
        except requests.exceptions.HTTPError as err:
            post_message_to_slack(err, sl_token)
            raise SystemExit(err)
        if (r.content) != '[]':
            jsonresp = json.loads(r.text)
            for item in jsonresp:
                repo_list.append(item['clone_url'])
            print ("[+]Added to list !\n")
        else:
            break
    print (f"List of all available repos: \n")
    for x in repo_list:
        print (x)
    print(f"\n\n{'*'*50}\n\n")
    for item in repo_list:
        y = item.split("//")
        url1 = "{}//{}:{}@{}".format(y[0],gh_uname,gh_token,y[1])
        cmd = "git clone {}".format(url1)
        os.system(cmd)
    scan_cloned_repos(sl_token)

def scan_cloned_repos(sl_token):
    all_files = []
    basepath = os.getcwd()
    print (f"\n\n{'*'*50}\n\nCurrent Working Directory: {basepath} \n\n{'*'*50}\n\n")
    folder_contents = os.listdir(basepath)
    print("List of all downloaded folders containing codes : \n")
    for items in folder_contents:
        if os.path.isdir(items):
            print (items)
    print (f"\n\n{'*'*50}\n")
    for items in folder_contents:
        if os.path.isdir(items):
            cmd = 'cd {} && gitleaks detect -v -f csv -r {}_result'.format(items,items)
            print (f"Running command: {cmd}\n")
            os.system(cmd)
            text = "Gitleaks report for {}".format(items)
            filename = '{}/{}/{}_result.csv'.format(basepath,items,items)
            newfile = '{}/{}/{}_report.csv'.format(basepath,items,items)
            print (f"Filename: {filename}")
            try:
                file_data = open(filename, "r")
                if os.path.getsize(filename) > 3:
                    df = pd.read_csv(filename)
                    df["Repo Name"] = items
                    df.to_csv(newfile, index=False)
                    all_files.append(newfile)
                    data = open(newfile,"r")
                    rsp = post_file_to_slack(text, '', data, sl_token)
                    print (rsp)
            except IOError as err:
                print (err)
            os.system('cd ..')
    merge_files(all_files,sl_token)

get_variables()


from jsonschema import validate as validate_schema
import json
from time import strptime
from hashlib import sha256
from passlib.utils.pbkdf2 import pbkdf2
from Crypto.Cipher import AES
import tempfile
import os.path
from shutil import rmtree
import subprocess
import os
import time

def decrypt_profile(ciphertext, passphrase):
  key = pbkdf2(bytes(passphrase.encode("utf-8")), sha256(b"DEBUG").hexdigest().encode("utf-8"), 2056, 32, "hmac-sha256")
  iv = ciphertext[0:16]
  decryptor = AES.new(key, AES.MODE_CBC, iv)
  plaintext = decryptor.decrypt(ciphertext[16:])
  try:
    return plaintext[:-plaintext[-1]].decode("utf-8")
  except UnicodeDecodeError:
    raise AssertionError("profile could not be decrypted")

def read_enc_json_file(path, pp):
  with open(path, "rb") as f:
    data = f.read()
  try:
    return json.loads(decrypt_profile(data, pp))
  except ValueError:
    raise AssertionError("profile contains invalid json")

def read_json_file(path):
  a = open(path)
  try:
    return json.load(a)
  except ValueError:
    raise AssertionError("profile contains invalid json")

def validate_profile_schema(profile):
  validate_schema(profile, SCHEMA)

def validate_profile_contents(profile):
  for i, n in enumerate(profile['notes']):
    if i > 0 and i < len(profile['notes'])-1:
      if not profile['notes'][i-1]['id'] < n['id'] < profile['notes'][i+1]['id']:
        raise AssertionError("object #"+str(i)+" id is out of order ("+str(profile['notes'][i-1]['id'])+", "+str(n['id'])+", "+str(profile['notes'][i+1]['id'])+")")
      if n['status'] not in STATUSES: raise AssertionError("")
    if n['id'] < 0: raise AssertionError("object #"+str(i)+" id is negative ("+str(n['id'])+")")
    try:
      strptime(n['last_touched'], DATEFMT)
    except ValueError:
      print(n)
      raise AssertionError("object #"+str(i)+" last_touched doesn't match time format "+DATEFMT)
    profile_ids = [n['id'] for n in profile['notes']]
    if len(profile_ids) != len(set(profile_ids)): raise AssertionError("there are duplicate IDs in 'notes'")

def compare_profile(clean, dirty):
  if not clean['encrypted'] == dirty['encrypted']: raise AssertionError()
  if not len(clean['notes']) == len(dirty['notes']): raise AssertionError()
  for c, d in zip(clean['notes'], dirty['notes']):
    if not c['id'] == d['id']: raise AssertionError()
    if not c['title'] == d['title']: raise AssertionError()
    if not c['status'] == d['status']: raise AssertionError()
    if not c['body'] == d['body']: raise AssertionError()
    # uh leaving last_touched for now...

def test_harness(tests):
  TMPDIR = tempfile.mkdtemp()
  devnull = open(os.devnull, "w")
  failed = 0

  print("# {}\n#    {}".format(tests['title'], tests['desc']))
  print("#\n# running {} tests.\n".format(len(tests['tests'])))
  start = time.clock()
  for t in tests['tests']:
    try:
      print("\ttest: "+t['name'], end="")
      cmd = [THECA_CMD]
      if not t["profile"] == "":
        cmd += ["-p", t["profile"]]
      if not t["profile_folder"] == "":
        cmd += ["-f", os.path.join(TMPDIR, t["profile_folder"])]
      else:
        cmd += ["-f", TMPDIR]
      
      if len(t["stdin"]) > 0:
        for c, s in zip(t["cmds"], t["stdin"]):
          if not s == None:
            p = subprocess.Popen(cmd+c, stdin=subprocess.PIPE, stdout=devnull)
            p.communicate(input=bytes(s.encode('utf-8')))
          else:
            subprocess.call(cmd+c, stdout=devnull)
      else:
        for c in t["cmds"]:
          subprocess.call(cmd+c, stdout=devnull)

      result_path = os.path.join(TMPDIR, t["result_path"])
      if t["result"]["encrypted"]:
        json_result = read_enc_json_file(result_path, t["result_passphrase"])
      else:
        json_result = read_json_file(result_path)
      validate_profile_schema(json_result)
      validate_profile_contents(json_result)
      compare_profile(t["result"], json_result)
      print(" [passed]")
    except (AssertionError, FileNotFoundError) as e:
      failed += 1
      print(" [failed]")

    # os.remove(result_path)
    for f_o in os.listdir(TMPDIR):
      f_o_p = os.path.join(TMPDIR, f_o)
      if os.path.isfile(f_o_p):
        os.unlink(f_o_p)
      else:
        shutil.rmtree(f_o_p)

  rmtree(TMPDIR)
  devnull.close()
  elapsed = time.clock()-start
  print("\n[passed: {}, failed {}, took: {:.2}s]\n".format(len(tests['tests'])-failed, failed, elapsed))
  return failed


GOOD_TESTS = {
  "title": "GOOD TESTS",
  "desc": "testing correct input.",
  "tests": [
    {
      "name": "new profile",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": []
      }
    },{
      "name": "add note",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": ""
          }
        ]
      }
    },{
      "name": "add full note (body from arg)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title", "-s", "-b", "test body"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "Started",
            "body": "test body"
          }
        ]
      }
    },{
      "name": "add full note (body from stdin)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title", "-s", "-"]
      ],
      "stdin": [
        None,
        "test body"
      ],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "Started",
            "body": "test body"
          }
        ]
      }
    },{
      "name": "add statuses",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "a"],
        ["add", "b", "-s"],
        ["add", "c", "-u"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "a",
            "status": "",
            "body": ""
          },{
            "id": 2,
            "title": "b",
            "status": "Started",
            "body": ""
          },{
            "id": 3,
            "title": "c",
            "status": "Urgent",
            "body": ""
          }
        ]
      }
    },{
      "name": "edit title",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title"],
        ["edit", "1", "new title"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "new title",
            "status": "",
            "body": ""
          }
        ]
      }
    },{
      "name": "edit statuses",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "finished", "-u"],
        ["add", "started"],
        ["add", "urgent"],
        ["edit", "1", "-n"],
        ["edit", "2", "-s"],
        ["edit", "3", "-u"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "finished",
            "status": "",
            "body": ""
          },{
            "id": 2,
            "title": "started",
            "status": "Started",
            "body": ""
          },{
            "id": 3,
            "title": "urgent",
            "status": "Urgent",
            "body": ""
          }
        ]
      }
    },{
      "name": "edit body (from arg)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title"],
        ["edit", "1", "-b", "a body yo"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": "a body yo"
          }
        ]
      }
    },{
      "name": "edit body (from stdin)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title"],
        ["edit", "1", "-"]
      ],
      "stdin": [
        None,
        None,
        "a body yo"
      ],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": "a body yo"
          }
        ]
      }
    },{
      "name": "edit everything (from args)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title"],
        ["edit", "1", "new title yo", "-b", "a body", "-s"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "new title yo",
            "status": "Started",
            "body": "a body"
          }
        ]
      }
    },{
      "name": "edit nothing",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title"],
        ["edit", "1"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": ""
          }
        ]
      }
    },{
      "name": "edit everything (from stdin)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title"],
        ["edit", "1", "new title yo", "-", "-s"]
      ],
      "stdin": [
        None,
        None,
        "a body yo"
      ],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "new title yo",
            "status": "Started",
            "body": "a body yo"
          }
        ]
      }
    },{
      "name": "delete note",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title"],
        ["del", "1"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": []
      }
    },{
      "name": "clear notes (yes from arg)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title"],
        ["add", "this is another title"],
        ["clear", "-y"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": []
      }
    },{
      "name": "clear notes (yes from stdin)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title"],
        ["add", "this is another title"],
        ["clear"]
      ],
      "stdin": [
        None,
        None,
        None,
        "y"
      ],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": []
      }
    },{
      "name": "transfer note (only title)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["new-profile", "second"],
        ["add", "this is the title"],
        ["transfer", "1", "to", "second"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": ""
          }
        ]
      }
    },
    {
      "name": "transfer note (title+body) (from arg)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["new-profile", "second"],
        ["add", "this is the title", "-b", "boody yo"],
        ["transfer", "1", "to", "second"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": "boody yo"
          }
        ]
      }
    },
    {
      "name": "transfer note (title+body) (from stdin)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["new-profile", "second"],
        ["add", "this is the title", "-"],
        ["transfer", "1", "to", "second"]
      ],
      "stdin": [
        None,
        None,
        "boody",
        None
      ],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": "boody"
          }
        ]
      }
    },{
      "name": "transfer note (title+status)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["new-profile", "second"],
        ["add", "this is the title", "-s"],
        ["transfer", "1", "to", "second"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "Started",
            "body": ""
          }
        ]
      }
    },{
      "name": "transfer note (title+status+body) (from arg)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["new-profile", "second"],
        ["add", "this is the title", "-s", "-b", "boody"],
        ["transfer", "1", "to", "second"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "Started",
            "body": "boody"
          }
        ]
      }
    },{
      "name": "transfer note (title+status+body) (from stdin)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["new-profile", "second"],
        ["add", "this is the title", "-s", "-"],
        ["transfer", "1", "to", "second"]
      ],
      "stdin": [
        None,
        None,
        "boody",
        None
      ],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "Started",
            "body": "boody"
          }
        ]
      }
    },{
      "name": "new profile 'second'",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": []
      }
    },{
      "name": "second profile, add note",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": ""
          }
        ]
      }
    },{
      "name": "second profile, add full note (body from arg)",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title", "-s", "-b", "test body"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "Started",
            "body": "test body"
          }
        ]
      }
    },{
      "name": "second profile, add full note (body from stdin)",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title", "-s", "-"]
      ],
      "stdin": [
        None,
        "test body"
      ],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "Started",
            "body": "test body"
          }
        ]
      }
    },{
      "name": "second profile, add statuses",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "a"],
        ["add", "b", "-s"],
        ["add", "c", "-u"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "a",
            "status": "",
            "body": ""
          },{
            "id": 2,
            "title": "b",
            "status": "Started",
            "body": ""
          },{
            "id": 3,
            "title": "c",
            "status": "Urgent",
            "body": ""
          }
        ]
      }
    },{
      "name": "second profile, edit title",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title"],
        ["edit", "1", "new title"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "new title",
            "status": "",
            "body": ""
          }
        ]
      }
    },{
      "name": "second profile, edit statuses",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "finished", "-u"],
        ["add", "started"],
        ["add", "urgent"],
        ["edit", "1", "-n"],
        ["edit", "2", "-s"],
        ["edit", "3", "-u"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "finished",
            "status": "",
            "body": ""
          },{
            "id": 2,
            "title": "started",
            "status": "Started",
            "body": ""
          },{
            "id": 3,
            "title": "urgent",
            "status": "Urgent",
            "body": ""
          }
        ]
      }
    },{
      "name": "second profile, edit body (from arg)",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title"],
        ["edit", "1", "-b", "a body yo"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": "a body yo"
          }
        ]
      }
    },{
      "name": "second profile, edit body (from stdin)",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title"],
        ["edit", "1", "-"]
      ],
      "stdin": [
        None,
        None,
        "a body yo"
      ],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": "a body yo"
          }
        ]
      }
    },{
      "name": "second profile, edit everything (from args)",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title"],
        ["edit", "1", "new title yo", "-b", "a body", "-s"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "new title yo",
            "status": "Started",
            "body": "a body"
          }
        ]
      }
    },{
      "name": "second profile, edit nothing",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title"],
        ["edit", "1"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": ""
          }
        ]
      }
    },{
      "name": "second profile, edit everything (from stdin)",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title"],
        ["edit", "1", "new title yo", "-", "-s"]
      ],
      "stdin": [
        None,
        None,
        "a body yo"
      ],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "new title yo",
            "status": "Started",
            "body": "a body yo"
          }
        ]
      }
    },{
      "name": "second profile, delete note",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title"],
        ["del", "1"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": []
      }
    },{
      "name": "second profile, clear notes (yes from arg)",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title"],
        ["add", "this is another title"],
        ["clear", "-y"]
      ],
      "stdin": [],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": []
      }
    },{
      "name": "second profile, clear notes (yes from stdin)",
      "profile": "second",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "second"],
        ["add", "this is the title"],
        ["add", "this is another title"],
        ["clear"]
      ],
      "stdin": [
        None,
        None,
        None,
        "y"
      ],
      "result_path": "second.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": []
      }
    },{
      "name": "new encrypted profile (key from args)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "enc", "-e", "-k", "DEBUG"],
      ],
      "stdin": [],
      "result_path": "enc.json",
      "result_passphrase": "DEBUG",
      "result": {
        "encrypted": True,
        "notes": []
      }
    },{
      "name": "new encrypted profile (key from stdin)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "enc", "-e"],
      ],
      "stdin": [
        "DEBUG"
      ],
      "result_path": "enc.json",
      "result_passphrase": "DEBUG",
      "result": {
        "encrypted": True,
        "notes": []
      }
    },{
      "name": "add note to encrypted profile (title only) (key from args)",
      "profile": "enc",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "enc", "-e", "-k", "DEBUG"],
        ["add", "encrypted title", "-k", "DEBUG"]
      ],
      "stdin": [],
      "result_path": "enc.json",
      "result_passphrase": "DEBUG",
      "result": {
        "encrypted": True,
        "notes": [
          {
            "id": 1,
            "title": "encrypted title",
            "status": "",
            "body": ""
          }
        ]
      }
    },{
      "name": "add note to encrypted profile (title only) (key from stdin)",
      "profile": "enc",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "enc", "-e"],
        ["add", "encrypted title", "-e"]
      ],
      "stdin": [
        "DEBUG",
        "DEBUG"
      ],
      "result_path": "enc.json",
      "result_passphrase": "DEBUG",
      "result": {
        "encrypted": True,
        "notes": [
          {
            "id": 1,
            "title": "encrypted title",
            "status": "",
            "body": ""
          }
        ]
      }
    },{
      "name": "add note to encrypted profile (title+body from args) (key from args)",
      "profile": "enc",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "enc", "-e", "-k", "DEBUG"],
        ["add", "encrypted title", "-b", "super secret", "-k", "DEBUG"]
      ],
      "stdin": [],
      "result_path": "enc.json",
      "result_passphrase": "DEBUG",
      "result": {
        "encrypted": True,
        "notes": [
          {
            "id": 1,
            "title": "encrypted title",
            "status": "",
            "body": "super secret"
          }
        ]
      }
    },{
      "name": "add note to encrypted profile (title+body from stdin) (key from stdin)",
      "profile": "enc",
      "profile_folder": "",
      "cmds": [
        ["new-profile", "enc", "-e"],
        ["add", "encrypted title", "-", "-e"]
      ],
      "stdin": [
        "DEBUG",
        "DEBUG\nsuper secret"
      ],
      "result_path": "enc.json",
      "result_passphrase": "DEBUG",
      "result": {
        "encrypted": True,
        "notes": [
          {
            "id": 1,
            "title": "encrypted title",
            "status": "",
            "body": "super secret"
          }
        ]
      }
    }
  ]
}

BAD_TESTS = {
  "title": "BAD TESTS",
  "desc": "testing incorrect input.",
  "tests": [
    {
      "name": "add note with no title",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": []
      }
    },{
      "name": "add note with no title and a status",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "-s"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": []
      }
    },{
      "name": "add note with no title and a status and a body (from arg)",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "-s", "-b", "haha bad"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": []
      }
    },{
      "name": "transfer note to profile that doesn't exist",
      "profile": "",
      "profile_folder": "",
      "cmds": [
        ["new-profile"],
        ["add", "this is the title"],
        ["transfer", "1", "to", "fakey"]
      ],
      "stdin": [],
      "result_path": "default.json",
      "result_passphrase": "",
      "result": {
        "encrypted": False,
        "notes": [
          {
            "id": 1,
            "title": "this is the title",
            "status": "",
            "body": ""
          }
        ]
      }
    }
    # "-" resolves to <title> here (i think because cmd_add and cmd__
    # interact werid? idk)
    # {
    #   "name": "add note with no title and a status and a body (from stdin)",
    #   "profile": "",
    #   "profile_folder": "",
    #   "cmds": [
    #     ["new-profile"],
    #     ["add", "-s", "-"]
    #   ],
    #   "stdin": [
    #     None,
    #     "hahah bad"
    #   ],
    #   "result_path": "default.json",
    #   "result_passphrase": "",
    #   "result": {
    #     "encrypted": False,
    #     "notes": []
    #   }
    # }
  ]
}

ALL_TESTS = [GOOD_TESTS, BAD_TESTS]

THECA_CMD = "target/theca"

STATUSES = ["", "Started", "Urgent"]
DATEFMT = "%Y-%m-%d %H:%M:%S %z"
SCHEMA = read_json_file("schema.json")

failed = 0

for t_set in ALL_TESTS:
  failed += test_harness(t_set)

test_sum = sum([len(T['tests']) for T in ALL_TESTS])
print("ran {} tests overall: {} passed, {} failed.\n".format(test_sum, test_sum-failed, failed))

if failed > 0:
  exit(1)

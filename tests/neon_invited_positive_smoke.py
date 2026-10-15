"""Opt-in live invited Neon authentication smoke check.

Run ONLY in a private runner with OS_TEST_EMAIL, OS_TEST_INVITE and OS_TEST_PASSWORD.
Never print request bodies, tokens, credentials or provider responses.
This is intentionally NOT executed on untrusted pull requests.
"""
import json, os, sys, urllib.request, urllib.error
BASE="https://ep-crimson-wildflower-b9rztglz.neonauth.c-7.eu-central-1.aws.neon.tech/obrasignal_auth/auth"
def post(path, body):
    request=urllib.request.Request(BASE+path, data=json.dumps(body).encode(),method="POST",headers={"Content-Type":"application/json","Origin":"https://obrasignal.com"})
    try:
        with urllib.request.urlopen(request,timeout=25) as r: return r.status,json.load(r)
    except urllib.error.HTTPError as error: return error.code,{}
def main():
    email=os.environ.get("OS_TEST_EMAIL","").strip().lower()
    invite=os.environ.get("OS_TEST_INVITE","")
    password=os.environ.get("OS_TEST_PASSWORD","")
    if not(email.endswith("@example.com") and invite.startswith("OS-") and len(invite)==51 and len(password)>=12):
        print("SKIP: private synthetic test inputs unavailable or invalid")
        return 2
    status, body=post("/sign-up/email",{"name":invite+"|Synthetic ObraSignal","email":email,"password":password})
    if not 200<=status<300: print("INVITED_SIGNUP_NOT_PROVEN",status);return 1
    print("INVITED_SIGNUP_ACCEPTED")
    status, body=post("/sign-in/email",{"email":email,"password":password})
    if not 200<=status<300: print("SIGNIN_NOT_PROVEN",status);return 1
    print("SIGNIN_ACCEPTED")
    if not isinstance(body,dict) or not(body.get("token") or body.get("user")):
        print("SESSION_FORMAT_NOT_PROVEN");return 1
    print("SESSION_RESPONSE_PRESENT; backend bearer verification remains separate")
    return 0
if __name__=="__main__":sys.exit(main())

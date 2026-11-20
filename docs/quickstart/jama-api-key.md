# Get Jama credentials

{.lead}
The tool signs in to Jama Connect with an API client ID and secret that you create from your profile.
It reads only what your Jama Connect account can see.

## Create the credentials

1. In Jama Connect, select your name in the header to open **My Profile**.
2. Select **Set API Credentials**.
3. Enter a name for the credentials, such as `Nominal checks`.
4. Select **Create API Credentials**.
5. Copy the client ID and the client secret. Jama Connect shows the secret only now.
6. Select **Close**.

% SCREENSHOT: My Profile, with Set API Credentials at the top
% SCREENSHOT: the new client ID and secret, after Create API Credentials

If you close the window before copying the secret, create new credentials.
Jama Connect's help has the same steps: [Set API credentials](https://help.jamasoftware.com/en/get-started/setting-up-your-work-environment/set-api-credentials.html).

## Use them

`init` asks for the client ID and secret:

```sh
python nominal-checks-from-jama.py init
```

It stores the secret on your computer, in your operating system's credential manager, under the name `nominal-checks-from-jama:` followed by your Jama Connect URL.
The secret isn't written to any file. To remove it, delete that entry in the credential manager.
To replace it, run `python nominal-checks-from-jama.py login`.

If Jama Connect refuses the credentials, ask your Jama Connect administrator to give your account access to the REST API.

:::{dropdown} Without API credentials
If you can't create API credentials, the tool can sign in with your Jama Connect username and password instead.
Instances that use single sign-on refuse this.

```sh
python nominal-checks-from-jama.py init --auth basic
```
:::

Jama Connect® is a registered trademark of Jama Software, Inc.

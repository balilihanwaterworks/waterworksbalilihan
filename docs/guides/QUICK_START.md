# QUICK START GUIDE
## 5-Minute Setup for Balilihan Waterworks

**For:** Quick reference when you need to get started fast
**Full Guide:** See `IMPLEMENTATION_CHECKLIST.md` for detailed instructions

---

## YOUR IMMEDIATE TASKS (Do in Order)

### ⚡ TASK 1: Get Gmail App Password (15 min)

```
1. Go to: https://myaccount.google.com/
2. Security → 2-Step Verification → TURN ON
3. Security → App passwords → Generate
4. App: Mail, Device: Other (Balilihan Waterworks)
5. COPY THE 16-CHARACTER CODE → Save it!
```

**Result:** You'll have something like: `abcd efgh ijkl mnop`
**Format it:** Remove spaces → `abcdefghijklmnop`

---

### ⚡ TASK 2: Configure Local .env File (2 min)

**Location:** `D:\balilihan_waterworks\waterworks\.env`

**Create file and add:**
```env
EMAIL_HOST_USER=your-gmail@gmail.com
EMAIL_HOST_PASSWORD=abcdefghijklmnop
DEFAULT_FROM_EMAIL=Balilihan Waterworks <noreply@balilihan-waterworks.com>
```

**Replace:**
- `your-gmail@gmail.com` → Your actual Gmail
- `abcdefghijklmnop` → Your 16-char app password (NO SPACES!)

---

### ⚡ TASK 3: Configure Railway (3 min)

**Go to:** https://railway.app/ → Your Project → Variables

**Add 3 variables:**
```
EMAIL_HOST_USER = your-gmail@gmail.com
EMAIL_HOST_PASSWORD = abcdefghijklmnop
DEFAULT_FROM_EMAIL = Balilihan Waterworks <noreply@balilihan-waterworks.com>
```

**Wait** for automatic redeployment (2-3 minutes)

---

### ⚡ TASK 4: Add Emails to Users (5 min)

**Run:**
```cmd
cd D:\balilihan_waterworks\waterworks
python manage.py shell
```

**Type:**
```python
from django.contrib.auth.models import User

# Add email to your superuser
user = User.objects.get(username='your_username_here')
user.email = 'your-email@gmail.com'
user.save()
print(f"✅ Email set for {user.username}")

# Add more users as needed
# user = User.objects.get(username='admin')
# user.email = 'admin@gmail.com'
# user.save()

exit()
```

---

### ⚡ TASK 5: Test It! (5 min)

**Test 1: Send Test Email**
```cmd
python manage.py shell
```

```python
from django.core.mail import send_mail
from django.conf import settings

send_mail(
    'Test Email',
    'If you receive this, email works!',
    settings.DEFAULT_FROM_EMAIL,
    ['your-email@gmail.com'],
)
# Should print: 1

exit()
```

**Check your inbox!** (Check spam folder too)

---

**Test 2: Try Password Reset**
```
1. Run: python manage.py runserver
2. Go to: http://localhost:8000/login/
3. Click: "Forgot Password?"
4. Enter your username
5. Check your email!
```

---

## TROUBLESHOOTING (1 minute fixes)

### ❌ Error: "SMTPAuthenticationError"
**Fix:** Check your app password has NO SPACES
```python
# In Django shell
from django.conf import settings
print(len(settings.EMAIL_HOST_PASSWORD))  # Should be 16
```

---

### ❌ Error: "No email address found"
**Fix:** Add email to user
```python
from django.contrib.auth.models import User
user = User.objects.get(username='username')
user.email = 'email@gmail.com'
user.save()
```

---

### ❌ Email doesn't arrive
**Fix:** Check spam folder (90% of the time it's there!)

---

### ❌ Can't find "App passwords" in Google
**Fix:**
1. Enable 2-Step Verification first
2. Wait 10 minutes
3. Refresh page

---

## VERIFICATION CHECKLIST

**Before you stop, verify:**

- ⬜ Gmail App Password generated (16 characters)
- ⬜ `.env` file created with credentials
- ⬜ Railway variables added
- ⬜ At least one user has email address
- ⬜ Test email received successfully
- ⬜ Password reset email received

**If all checked ✅ → You're done!**

---

## FILES YOU NEED

**Configuration:**
- `.env` (local) - Add email credentials
- Railway Variables (production) - Same credentials

**Documentation:**
- `IMPLEMENTATION_CHECKLIST.md` - Full detailed guide
- `EMAIL_SETUP_GUIDE.md` - Detailed email setup
- `SYSTEM_EVENT_LIST.md` - All system events (thesis)

---

## MOST COMMON MISTAKES

1. ❌ Using regular Gmail password instead of app password
2. ❌ Spaces in the app password (`abcd efgh` instead of `abcdefgh`)
3. ❌ Forgetting to add emails to user accounts
4. ❌ Not checking spam folder
5. ❌ Not enabling 2-Step Verification before generating app password

---

## NEED MORE HELP?

**Read the full guide:**
```
docs/IMPLEMENTATION_CHECKLIST.md
```

**Search for specific errors:**
- Copy the error message
- Google: "django [error message]"

**Check specific guides:**
- Email issues → `docs/EMAIL_SETUP_GUIDE.md`
- System events → `docs/SYSTEM_EVENT_LIST.md`
- User roles → `docs/USER_ROLE_FLOWCHARTS.md`

---

## TIME ESTIMATE

**Total time needed:** 30-45 minutes

| Task | Time |
|------|------|
| Gmail setup | 15 min |
| Local config | 2 min |
| Railway config | 3 min |
| Add user emails | 5 min |
| Testing | 5 min |
| **Total** | **30 min** |

---

**🚀 You've got this! Start with Task 1 and work your way down.**

---

**End of Quick Start**

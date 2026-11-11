# Auth Testing Playbook
Step 1: MongoDB
```
mongosh test_database --eval 'db.users.findOne({role:"admin"},{password_hash:1})'
```
Verify bcrypt hash starts with `$2b$`, indexes on users.email (unique), login_attempts.identifier, email_tokens.expires_at (TTL).

Step 2: API
```
curl -c cookies.txt -X POST $URL/api/auth/login -H "Content-Type: application/json" -d '{"email":"admin@aetheria.io","password":"Admin@12345"}'
curl -b cookies.txt $URL/api/auth/me
```
Login returns user object and sets access_token + refresh_token cookies. /me returns same user.
5 failed logins for the same ip:email -> 429 lockout for 15 minutes.

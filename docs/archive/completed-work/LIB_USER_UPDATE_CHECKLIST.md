# Library User Update - Quick Checklist

**Print this page and check off items as you complete them.**

---

## Pre-Update (5 minutes)

- [ ] Backup current code: `git commit -am "backup before library update"`
- [ ] Note current library version/commit: `cd arango-entity-resolution && git log -1 --oneline`
- [ ] Document current database credentials
- [ ] Ensure database is accessible

---

## Update Library (5 minutes)

Choose one method:

**Method A: Git Submodule**
- [ ] `cd /path/to/your/project`
- [ ] `git submodule update --remote arango-entity-resolution`
- [ ] `git add arango-entity-resolution`
- [ ] `git commit -m "chore: update entity-resolution library"`

**Method B: Direct Copy**
- [ ] `cd /path/to/your/project`
- [ ] `mv arango-entity-resolution arango-entity-resolution-backup`
- [ ] `git clone <repo-url> arango-entity-resolution`

**Method C: Python Package**
- [ ] `pip install --upgrade /path/to/arango-entity-resolution`

---

## Configure Environment (10 minutes)

- [ ] Create `.env` file in your project root:
```bash
ARANGO_HOST=localhost
ARANGO_PORT=8529
ARANGO_USERNAME=root
ARANGO_ROOT_PASSWORD=your_password_here
ARANGO_DATABASE=your_database_name
```

- [ ] Add to `.gitignore`:
```bash
echo ".env" >> .gitignore
echo "config.json" >> .gitignore
```

- [ ] Install python-dotenv: `pip install python-dotenv`

- [ ] Update your application code to load environment:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## Test (10 minutes)

- [ ] Test connection:
```bash
python -c "
from entity_resolution.utils.database import test_database_connection
print('✓ Connected' if test_database_connection() else '✗ Failed')
"
```

- [ ] Test your existing workflow with sample data

- [ ] Verify no errors in application logs

- [ ] Run your test suite (if you have one)

---

## Optional: Enable Bulk Processing (5 minutes)

**Only if processing > 50K records**

- [ ] Update code to use `BulkBlockingService`
- [ ] Test with small limit first (e.g., limit=1000)
- [ ] Benchmark performance improvement
- [ ] Update to full dataset when confident

---

## Deploy (5 minutes)

- [ ] Commit changes: `git commit -am "feat: update to latest entity-resolution library"`
- [ ] Test in staging environment (if available)
- [ ] Deploy to production
- [ ] Monitor application logs
- [ ] Verify performance improvements (if using bulk processing)

---

## Post-Update

- [ ] Document changes in your project changelog
- [ ] Notify team of new features available
- [ ] Remove backup: `rm -rf arango-entity-resolution-backup` (when confident)
- [ ] Update your project documentation (if needed)

---

## If Something Goes Wrong

**Rollback Steps:**
1. [ ] `cd /path/to/your/project`
2. [ ] `cd arango-entity-resolution`
3. [ ] `git checkout <previous-commit-hash>`
4. [ ] Restart application
5. [ ] Verify working
6. [ ] Report issue

**OR restore backup:**
1. [ ] `rm -rf arango-entity-resolution`
2. [ ] `mv arango-entity-resolution-backup arango-entity-resolution`
3. [ ] Restart application

---

## Quick Reference

**Library location in your project:** _______________________________________________

**Previous commit/version:** _______________________________________________

**Database connection:**
- Host: _______________________________________________
- Database: _______________________________________________

**Contact for help:** _______________________________________________

**Update performed by:** _______________________________________________ 

**Date:** _______________________________________________

---

## Success Criteria

✓ Application starts without errors  
✓ Database connection works  
✓ Existing functionality unchanged  
✓ Performance improved (if using bulk processing)  
✓ No security warnings about credentials  

---

**Total Time:** ~30 minutes  
**Risk:** LOW (non-breaking update)  
**Rollback:** Easy (see above)

**For detailed instructions, see:** `LIB_USER_UPDATE_GUIDE.md`


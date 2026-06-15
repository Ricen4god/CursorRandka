import logging
from datetime import date, datetime, timedelta

import aiosqlite

from config import (
    ADMIN_ID,
    DB_PATH,
    DAILY_LIKE_LIMIT,
    FEED_RESET_HOURS,
    MIN_AGE,
    PREMIUM_DAYS,
    resolve_nearby_cities,
)
from premium import age_range_for, daily_like_limit_for, is_premium_active

logger = logging.getLogger(__name__)


async def _migrate_db(db):
    cursor = await db.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in await cursor.fetchall()}

    if "search_city" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN search_city TEXT")
        await db.execute(
            "UPDATE users SET search_city = city WHERE search_city IS NULL OR TRIM(search_city) = ''"
        )

    if "is_shadow_banned" not in columns:
        await db.execute(
            "ALTER TABLE users ADD COLUMN is_shadow_banned INTEGER NOT NULL DEFAULT 0"
        )

    if "ban_reason" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN ban_reason TEXT")

    if "last_active" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN last_active TEXT")
        await db.execute(
            "UPDATE users SET last_active = created_at WHERE last_active IS NULL"
        )

    if "feed_in_nearby" not in columns:
        await db.execute(
            "ALTER TABLE users ADD COLUMN feed_in_nearby INTEGER NOT NULL DEFAULT 0"
        )

    if "feed_local_exhausted_at" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN feed_local_exhausted_at TEXT")

    if "browse_nearby_since" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN browse_nearby_since TEXT")

    if "premium_until" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN premium_until TEXT")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            stripe_session_id TEXT,
            stripe_subscription_id TEXT,
            amount_grosze INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'pln',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS skip_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            viewer_id INTEGER NOT NULL,
            skipped_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS daily_rewinds (
            user_id INTEGER NOT NULL,
            rewind_date TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, rewind_date)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS daily_superlikes (
            user_id INTEGER NOT NULL,
            like_date TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, like_date)
        )
    """)

    cursor = await db.execute("PRAGMA table_info(reports)")
    report_columns = {row[1] for row in await cursor.fetchall()}
    if "status" not in report_columns:
        await db.execute(
            "ALTER TABLE reports ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"
        )

    await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_id INTEGER,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                looking_for TEXT NOT NULL,
                city TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                device_type TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                bio TEXT NOT NULL DEFAULT '',
                photo_file_id TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_banned INTEGER NOT NULL DEFAULT 0,
                is_shadow_banned INTEGER NOT NULL DEFAULT 0,
                ban_reason TEXT,
                views_count INTEGER NOT NULL DEFAULT 0,
                likes_received INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_active TEXT,
                search_city TEXT,
                feed_in_nearby INTEGER NOT NULL DEFAULT 0,
                feed_local_exhausted_at TEXT,
                browse_nearby_since TEXT,
                premium_until TEXT
            );

            CREATE TABLE IF NOT EXISTS views (
                viewer_id INTEGER NOT NULL,
                viewed_id INTEGER NOT NULL,
                viewed_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (viewer_id, viewed_id)
            );

            CREATE TABLE IF NOT EXISTS likes (
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (from_user_id, to_user_id)
            );

            CREATE TABLE IF NOT EXISTS daily_likes (
                user_id INTEGER NOT NULL,
                like_date TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, like_date)
            );

            CREATE TABLE IF NOT EXISTS matches (
                user1_id INTEGER NOT NULL,
                user2_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user1_id, user2_id)
            );

            CREATE TABLE IF NOT EXISTS blocks (
                blocker_id INTEGER NOT NULL,
                blocked_id INTEGER NOT NULL,
                PRIMARY KEY (blocker_id, blocked_id)
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER NOT NULL,
                reported_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS admin_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_id INTEGER,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        await _migrate_db(db)
        await db.commit()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID and ADMIN_ID != 0


def user_search_city(user: dict) -> str:
    return user.get("search_city") or user.get("city") or ""


async def log_admin_action(
    admin_id: int,
    action: str,
    target_id: int | None = None,
    details: str | None = None,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO admin_log (admin_id, action, target_id, details)
               VALUES (?, ?, ?, ?)""",
            (admin_id, action, target_id, details),
        )
        await db.commit()
    logger.info(
        "Admin action: admin=%s action=%s target=%s details=%s",
        admin_id,
        action,
        target_id,
        details,
    )


async def touch_last_active(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_active = datetime('now') WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_user(data: dict):
    search_city = data.get("search_city") or data["city"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users
               (user_id, username, age, gender, looking_for, city,
                latitude, longitude, device_type, name, bio, photo_file_id,
                search_city, last_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                data["user_id"],
                data.get("username"),
                data["age"],
                data["gender"],
                data["looking_for"],
                data["city"],
                None,
                None,
                "",
                data["name"],
                data["bio"],
                data["photo_file_id"],
                search_city,
            ),
        )
        await db.commit()
    await _refresh_searchers_after_new_city_user(data["city"])


async def _refresh_searchers_after_new_city_user(city: str):
    """Reset nearby mode + local views when someone new joins a search city."""
    city = (city or "").strip()
    if not city:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT user_id, COALESCE(search_city, city) AS search_city
               FROM users
               WHERE browse_nearby_since IS NOT NULL
                 AND LOWER(TRIM(COALESCE(search_city, city))) = LOWER(TRIM(?))""",
            (city,),
        ) as cur:
            searchers = await cur.fetchall()

    for row in searchers:
        cleared = await clear_views_for_city(row["user_id"], row["search_city"])
        await update_user(row["user_id"], browse_nearby_since=None)
        logger.info(
            "New user in %s — reset local feed for searcher %s (cleared %s views)",
            city,
            row["user_id"],
            cleared,
        )


async def update_user(user_id: int, **fields):
    if not fields:
        return
    if "latitude" in fields or "longitude" in fields:
        fields.pop("latitude", None)
        fields.pop("longitude", None)
    if "search_city" in fields:
        fields["browse_nearby_since"] = None
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {cols} WHERE user_id = ?", vals)
        await db.commit()


async def delete_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.execute(
            "DELETE FROM views WHERE viewer_id = ? OR viewed_id = ?",
            (user_id, user_id),
        )
        await db.execute(
            "DELETE FROM likes WHERE from_user_id = ? OR to_user_id = ?",
            (user_id, user_id),
        )
        await db.execute("DELETE FROM daily_likes WHERE user_id = ?", (user_id,))
        await db.execute(
            "DELETE FROM matches WHERE user1_id = ? OR user2_id = ?",
            (user_id, user_id),
        )
        await db.execute(
            "DELETE FROM blocks WHERE blocker_id = ? OR blocked_id = ?",
            (user_id, user_id),
        )
        await db.execute(
            "DELETE FROM reports WHERE reporter_id = ? OR reported_id = ?",
            (user_id, user_id),
        )
        await db.commit()


def _gender_match(user: dict, candidate: dict) -> bool:
    user_wants = user["looking_for"]
    cand_wants = candidate["looking_for"]
    user_g = user["gender"]
    cand_g = candidate["gender"]

    user_ok = cand_g == user_wants or user_wants == "both"
    cand_ok = user_g == cand_wants or cand_wants == "both"
    return user_ok and cand_ok


def _candidate_base_sql(cities: list[str] | None = None) -> tuple[str, list]:
    city_filter_sql = ""
    params: list = []

    if cities:
        if len(cities) == 1:
            city_filter_sql = "AND LOWER(TRIM(u.city)) = LOWER(TRIM(?))"
            params.append(cities[0])
        else:
            placeholders = ", ".join("?" * len(cities))
            city_filter_sql = f"AND LOWER(TRIM(u.city)) IN ({placeholders})"
            params.extend(c.lower().strip() for c in cities)

    sql = f"""SELECT u.* FROM users u
               WHERE u.user_id != ?
                 {city_filter_sql}
                 AND u.is_active = 1
                 AND u.is_banned = 0
                 AND u.is_shadow_banned = 0
                 AND u.age BETWEEN ? AND ?
                 AND u.user_id NOT IN (
                     SELECT blocked_id FROM blocks WHERE blocker_id = ?
                 )
                 AND u.user_id NOT IN (
                     SELECT blocker_id FROM blocks WHERE blocked_id = ?
                 )"""
    return sql, params


async def clear_views_for_city(viewer_id: int, city: str) -> int:
    city = (city or "").strip()
    if not city:
        return 0
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT COUNT(*) FROM views v
               JOIN users u ON u.user_id = v.viewed_id
               WHERE v.viewer_id = ?
                 AND LOWER(TRIM(u.city)) = LOWER(TRIM(?))""",
            (viewer_id, city),
        ) as cur:
            count = (await cur.fetchone())[0]
        await db.execute(
            """DELETE FROM views
               WHERE viewer_id = ?
                 AND viewed_id IN (
                     SELECT user_id FROM users
                     WHERE LOWER(TRIM(city)) = LOWER(TRIM(?))
                 )""",
            (viewer_id, city),
        )
        await db.commit()
    return count


async def _has_new_user_in_city_since(city: str, since: str) -> bool:
    city = (city or "").strip()
    if not city or not since:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT 1 FROM users
               WHERE LOWER(TRIM(city)) = LOWER(TRIM(?))
                 AND datetime(created_at) > datetime(?)
               LIMIT 1""",
            (city, since),
        ) as cur:
            return await cur.fetchone() is not None


async def _should_reset_local_feed(search_city: str, nearby_since: str | None) -> bool:
    if not nearby_since or not (search_city or "").strip():
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT CASE
                   WHEN datetime(?, '+' || ? || ' hours') <= datetime('now')
                   THEN 1 ELSE 0 END""",
            (nearby_since, FEED_RESET_HOURS),
        ) as cur:
            if (await cur.fetchone())[0]:
                return True
    if await _has_new_user_in_city_since(search_city, nearby_since):
        return True
    return False


def _feed_notice_to_local(search_city: str, *, new_user: bool) -> str:
    if new_user:
        return (
            f"Nowa osoba w {search_city}! 🎉\n"
            f"Wracamy do lokalnych profili — zobaczysz też wcześniejsze."
        )
    return (
        f"Wracamy do profili z {search_city}! 🏙️\n"
        f"Zobaczysz też osoby, które oglądałeś/aś wcześniej."
    )


def _feed_notice_to_nearby(search_city: str) -> str:
    return (
        f"Brak nowych osób w {search_city} 😔\n"
        f"Rozszerzam wyszukiwanie na pobliskie miasta 📍"
    )


async def _fetch_unviewed_candidates(
    user: dict, cities: list[str] | None, limit: int
) -> list[dict]:
    user_id = user["user_id"]
    user_age = user["age"]
    span = age_range_for(user)
    min_age = max(MIN_AGE, user_age - span)
    max_age = user_age + span

    base_sql, extra_params = _candidate_base_sql(cities)
    params: list = [user_id, *extra_params, min_age, max_age, user_id, user_id, user_id]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""{base_sql}
                 AND u.user_id NOT IN (
                     SELECT viewed_id FROM views WHERE viewer_id = ?
                 )
               ORDER BY
                 CASE
                   WHEN u.premium_until IS NOT NULL
                    AND datetime(u.premium_until) > datetime('now')
                   THEN 0 ELSE 1
                 END,
                 RANDOM()
               LIMIT 50""",
            tuple(params),
        ) as cur:
            rows = await cur.fetchall()

    result = []
    for row in rows:
        cand = dict(row)
        if _gender_match(user, cand):
            result.append(cand)
            if len(result) >= limit:
                break
    return result


async def clear_views(viewer_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM views WHERE viewer_id = ?", (viewer_id,)
        ) as cur:
            count = (await cur.fetchone())[0]
        await db.execute("DELETE FROM views WHERE viewer_id = ?", (viewer_id,))
        await db.commit()
    return count


async def diagnose_candidates(user_id: int) -> dict:
    user = await get_user(user_id)
    if not user:
        return {"reason": "no_user"}

    user_age = user["age"]
    span = age_range_for(user)
    min_age = max(MIN_AGE, user_age - span)
    max_age = user_age + span
    search_city = user_search_city(user).strip()
    nearby_since = user.get("browse_nearby_since")
    in_nearby_mode = bool(nearby_since)

    if in_nearby_mode:
        cities = resolve_nearby_cities(search_city)
        mode = "nearby"
    else:
        cities = [search_city] if search_city else None
        mode = "local"

    base_sql, extra_params = _candidate_base_sql(cities)
    params = [user_id, *extra_params, min_age, max_age, user_id, user_id]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(base_sql, tuple(params)) as cur:
            all_rows = [dict(row) for row in await cur.fetchall()]

        async with db.execute(
            "SELECT viewed_id FROM views WHERE viewer_id = ?", (user_id,)
        ) as cur:
            viewed_ids = {row[0] for row in await cur.fetchall()}

    gender_ok = [r for r in all_rows if _gender_match(user, r)]
    unviewed = [r for r in gender_ok if r["user_id"] not in viewed_ids]

    local_exhausted = False
    if search_city and not in_nearby_mode:
        local_rows = [
            r
            for r in all_rows
            if r["city"].strip().lower() == search_city.lower()
        ]
        local_gender_ok = [r for r in local_rows if _gender_match(user, r)]
        local_unviewed = [r for r in local_gender_ok if r["user_id"] not in viewed_ids]
        local_exhausted = len(local_gender_ok) > 0 and len(local_unviewed) == 0

    return {
        "search_city": search_city,
        "feed_mode": mode,
        "in_nearby_mode": in_nearby_mode,
        "age_range": (min_age, max_age),
        "user_gender": user["gender"],
        "user_looking_for": user["looking_for"],
        "total_in_city_age": len(all_rows),
        "after_gender_filter": len(gender_ok),
        "after_views_filter": len(unviewed),
        "viewed_count": len(viewed_ids),
        "all_viewed": len(gender_ok) > 0 and len(unviewed) == 0,
        "local_exhausted": local_exhausted,
        "no_city_matches": len(all_rows) == 0,
        "no_gender_matches": len(all_rows) > 0 and len(gender_ok) == 0,
    }


async def get_candidates(
    user_id: int, limit: int = 1
) -> tuple[list[dict], str | None]:
    user = await get_user(user_id)
    if not user:
        return [], None

    search_city = user_search_city(user).strip()
    nearby_since = user.get("browse_nearby_since")
    notice: str | None = None

    if nearby_since and await _should_reset_local_feed(search_city, nearby_since):
        new_user = await _has_new_user_in_city_since(search_city, nearby_since)
        cleared = await clear_views_for_city(user_id, search_city)
        await update_user(user_id, browse_nearby_since=None)
        nearby_since = None
        notice = _feed_notice_to_local(search_city, new_user=new_user)
        logger.info(
            "Local feed reset for user %s city=%s cleared=%s new_user=%s",
            user_id,
            search_city,
            cleared,
            new_user,
        )

    if nearby_since:
        nearby = resolve_nearby_cities(search_city)
        result = await _fetch_unviewed_candidates(user, nearby or None, limit)
        if not result:
            diag = await diagnose_candidates(user_id)
            logger.debug(
                "No nearby candidates for user %s: city=%s nearby=%s unviewed=%s",
                user_id,
                search_city,
                nearby,
                diag.get("after_views_filter"),
            )
        return result, notice

    local_cities = [search_city] if search_city else None
    result = await _fetch_unviewed_candidates(user, local_cities, limit)
    if result:
        return result, notice

    diag = await diagnose_candidates(user_id)
    logger.debug(
        "No candidates for user %s: city=%s age=%s-%s gender=%s wants=%s "
        "in_city=%s gender_ok=%s unviewed=%s viewed=%s",
        user_id,
        diag.get("search_city"),
        diag.get("age_range", (None, None))[0],
        diag.get("age_range", (None, None))[1],
        diag.get("user_gender"),
        diag.get("user_looking_for"),
        diag.get("total_in_city_age"),
        diag.get("after_gender_filter"),
        diag.get("after_views_filter"),
        diag.get("viewed_count"),
    )

    if diag.get("local_exhausted") or diag.get("all_viewed"):
        nearby = resolve_nearby_cities(search_city)
        if nearby:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE users SET browse_nearby_since = datetime('now') WHERE user_id = ?",
                    (user_id,),
                )
                await db.commit()
            switch_notice = _feed_notice_to_nearby(search_city)
            notice = switch_notice if not notice else f"{notice}\n\n{switch_notice}"
            result = await _fetch_unviewed_candidates(user, nearby, limit)
            logger.info(
                "User %s switched to nearby feed for %s -> %s",
                user_id,
                search_city,
                nearby,
            )

    return result, notice


async def record_view(viewer_id: int, viewed_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO views (viewer_id, viewed_id) VALUES (?, ?)",
            (viewer_id, viewed_id),
        )
        await db.execute(
            "UPDATE users SET views_count = views_count + 1 WHERE user_id = ?",
            (viewed_id,),
        )
        await db.execute(
            """UPDATE users SET last_active = datetime('now')
               WHERE user_id IN (?, ?)""",
            (viewer_id, viewed_id),
        )
        await db.commit()


async def get_daily_likes_count(user_id: int) -> int:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM daily_likes WHERE user_id = ? AND like_date = ?",
            (user_id, today),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def increment_daily_likes(user_id: int) -> bool:
    user = await get_user(user_id)
    limit = daily_like_limit_for(user)
    if limit is None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET last_active = datetime('now') WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()
        return True

    today = date.today().isoformat()
    current = await get_daily_likes_count(user_id)
    if current >= limit:
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO daily_likes (user_id, like_date, count)
               VALUES (?, ?, 1)
               ON CONFLICT(user_id, like_date)
               DO UPDATE SET count = count + 1""",
            (user_id, today),
        )
        await db.execute(
            "UPDATE users SET last_active = datetime('now') WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
    return True


async def activate_premium(user_id: int, days: int = PREMIUM_DAYS) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT premium_until FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        base = row[0] if row and row[0] else None
        if base:
            try:
                start = datetime.fromisoformat(base)
                if start > datetime.utcnow():
                    anchor = start
                else:
                    anchor = datetime.utcnow()
            except ValueError:
                anchor = datetime.utcnow()
        else:
            anchor = datetime.utcnow()

        new_until = (anchor + timedelta(days=days)).isoformat(timespec="seconds")
        await db.execute(
            "UPDATE users SET premium_until = ? WHERE user_id = ?",
            (new_until, user_id),
        )
        await db.commit()
    return new_until


async def get_likers(user_id: int) -> list[dict]:
    """Users who liked me but no mutual match yet and I haven't liked them."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT u.* FROM likes l
               JOIN users u ON u.user_id = l.from_user_id
               WHERE l.to_user_id = ?
                 AND u.is_banned = 0
                 AND u.is_shadow_banned = 0
                 AND NOT EXISTS (
                     SELECT 1 FROM likes l2
                     WHERE l2.from_user_id = ? AND l2.to_user_id = l.from_user_id
                 )
                 AND NOT EXISTS (
                     SELECT 1 FROM blocks b
                     WHERE (b.blocker_id = ? AND b.blocked_id = l.from_user_id)
                        OR (b.blocker_id = l.from_user_id AND b.blocked_id = ?)
                 )
               ORDER BY l.created_at DESC""",
            (user_id, user_id, user_id, user_id),
        ) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def record_skip(viewer_id: int, skipped_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO skip_history (viewer_id, skipped_id) VALUES (?, ?)",
            (viewer_id, skipped_id),
        )
        await db.commit()


async def get_last_skip(viewer_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT sh.*, u.name, u.age, u.city, u.photo_file_id
               FROM skip_history sh
               JOIN users u ON u.user_id = sh.skipped_id
               WHERE sh.viewer_id = ?
               ORDER BY sh.id DESC LIMIT 1""",
            (viewer_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def undo_last_skip(viewer_id: int) -> dict | None:
    last = await get_last_skip(viewer_id)
    if not last:
        return None
    skipped_id = last["skipped_id"]
    history_id = last["id"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM views WHERE viewer_id = ? AND viewed_id = ?",
            (viewer_id, skipped_id),
        )
        await db.execute("DELETE FROM skip_history WHERE id = ?", (history_id,))
        await db.commit()
    user = await get_user(skipped_id)
    return user


async def get_daily_rewinds_count(user_id: int) -> int:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM daily_rewinds WHERE user_id = ? AND rewind_date = ?",
            (user_id, today),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def increment_daily_rewinds(user_id: int) -> bool:
    from config import DAILY_REWIND_LIMIT

    today = date.today().isoformat()
    current = await get_daily_rewinds_count(user_id)
    if current >= DAILY_REWIND_LIMIT:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO daily_rewinds (user_id, rewind_date, count)
               VALUES (?, ?, 1)
               ON CONFLICT(user_id, rewind_date)
               DO UPDATE SET count = count + 1""",
            (user_id, today),
        )
        await db.commit()
    return True


async def get_daily_superlikes_count(user_id: int) -> int:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM daily_superlikes WHERE user_id = ? AND like_date = ?",
            (user_id, today),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def increment_daily_superlikes(user_id: int) -> bool:
    from config import DAILY_SUPERLIKE_LIMIT

    today = date.today().isoformat()
    current = await get_daily_superlikes_count(user_id)
    if current >= DAILY_SUPERLIKE_LIMIT:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO daily_superlikes (user_id, like_date, count)
               VALUES (?, ?, 1)
               ON CONFLICT(user_id, like_date)
               DO UPDATE SET count = count + 1""",
            (user_id, today),
        )
        await db.commit()
    return True


async def record_payment(
    user_id: int,
    amount_grosze: int,
    stripe_session_id: str | None = None,
    status: str = "pending",
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO payments (user_id, stripe_session_id, amount_grosze, status)
               VALUES (?, ?, ?, ?)""",
            (user_id, stripe_session_id, amount_grosze, status),
        )
        await db.commit()
        return cur.lastrowid


async def mark_payment_completed(stripe_session_id: str, subscription_id: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE payments SET status = 'completed',
                   stripe_subscription_id = COALESCE(?, stripe_subscription_id)
               WHERE stripe_session_id = ?""",
            (subscription_id, stripe_session_id),
        )
        await db.commit()


async def get_views_last_7_days(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT COUNT(*) FROM views
               WHERE viewed_id = ?
                 AND datetime(viewed_at) >= datetime('now', '-7 days')""",
            (user_id,),
        ) as cur:
            return (await cur.fetchone())[0]


async def can_like_today(user_id: int) -> tuple[bool, int | None]:
    """Returns (allowed, limit or None if unlimited)."""
    user = await get_user(user_id)
    limit = daily_like_limit_for(user)
    if limit is None:
        return True, None
    count = await get_daily_likes_count(user_id)
    return count < limit, limit


async def add_like(from_id: int, to_id: int, message: str | None = None) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM likes WHERE from_user_id = ? AND to_user_id = ?",
            (from_id, to_id),
        ) as cur:
            if await cur.fetchone():
                return False

        await db.execute(
            "INSERT INTO likes (from_user_id, to_user_id, message) VALUES (?, ?, ?)",
            (from_id, to_id, message),
        )
        await db.execute(
            "UPDATE users SET likes_received = likes_received + 1 WHERE user_id = ?",
            (to_id,),
        )
        await db.execute(
            "UPDATE users SET last_active = datetime('now') WHERE user_id = ?",
            (from_id,),
        )

        async with db.execute(
            "SELECT 1 FROM likes WHERE from_user_id = ? AND to_user_id = ?",
            (to_id, from_id),
        ) as cur:
            mutual = await cur.fetchone()

        if mutual:
            u1, u2 = min(from_id, to_id), max(from_id, to_id)
            await db.execute(
                "INSERT OR IGNORE INTO matches (user1_id, user2_id) VALUES (?, ?)",
                (u1, u2),
            )
            await db.commit()
            return True

        await db.commit()
        return False


async def get_matches(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT u.* FROM users u
               JOIN matches m ON (
                   (m.user1_id = ? AND m.user2_id = u.user_id) OR
                   (m.user2_id = ? AND m.user1_id = u.user_id)
               )
               ORDER BY m.created_at DESC""",
            (user_id, user_id),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def is_blocked(blocker_id: int, blocked_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM blocks WHERE blocker_id = ? AND blocked_id = ?",
            (blocker_id, blocked_id),
        ) as cur:
            return await cur.fetchone() is not None


async def block_user(blocker_id: int, blocked_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO blocks (blocker_id, blocked_id) VALUES (?, ?)",
            (blocker_id, blocked_id),
        )
        await db.commit()


async def unblock_user(blocker_id: int, blocked_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM blocks WHERE blocker_id = ? AND blocked_id = ?",
            (blocker_id, blocked_id),
        )
        await db.commit()


async def get_blocked_ids(blocker_id: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT blocked_id FROM blocks WHERE blocker_id = ?",
            (blocker_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [row[0] for row in rows]


async def add_report(reporter_id: int, reported_id: int, reason: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO reports (reporter_id, reported_id, reason, status)
               VALUES (?, ?, ?, 'pending')""",
            (reporter_id, reported_id, reason),
        )
        await db.commit()


async def ban_user(user_id: int, reason: str | None = None, shadow: bool = False):
    if shadow:
        await update_user(
            user_id,
            is_shadow_banned=1,
            ban_reason=reason,
        )
    else:
        await update_user(
            user_id,
            is_banned=1,
            is_active=0,
            is_shadow_banned=0,
            ban_reason=reason,
        )


async def unban_user(user_id: int):
    await update_user(
        user_id,
        is_banned=0,
        is_shadow_banned=0,
        ban_reason=None,
    )


async def set_shadow_ban(user_id: int, enabled: bool, reason: str | None = None):
    if enabled:
        await update_user(
            user_id,
            is_shadow_banned=1,
            ban_reason=reason,
        )
    else:
        await update_user(user_id, is_shadow_banned=0)


async def get_stats() -> dict:
    stats = await get_admin_stats()
    return {
        "total_users": stats["total_users"],
        "active_users": stats["active_profiles"],
        "total_matches": stats["total_matches"],
        "total_reports": stats["pending_reports"],
        "new_today": stats["registrations_today"],
    }


async def get_admin_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0]

        async with db.execute(
            """SELECT COUNT(*) FROM users
               WHERE datetime(COALESCE(last_active, created_at)) >= datetime('now', '-1 day')"""
        ) as cur:
            active_today = (await cur.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1") as cur:
            active_profiles = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE is_active = 0 AND is_banned = 0"
        ) as cur:
            paused_profiles = (await cur.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM likes") as cur:
            total_likes = (await cur.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM matches") as cur:
            total_matches = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM reports WHERE status = 'pending'"
        ) as cur:
            pending_reports = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')"
        ) as cur:
            registrations_today = (await cur.fetchone())[0]

        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT city, COUNT(*) AS cnt FROM users
               GROUP BY LOWER(TRIM(city))
               ORDER BY cnt DESC
               LIMIT 5"""
        ) as cur:
            top_cities = [dict(row) for row in await cur.fetchall()]

    return {
        "total_users": total_users,
        "active_today": active_today,
        "active_profiles": active_profiles,
        "paused_profiles": paused_profiles,
        "total_likes": total_likes,
        "total_matches": total_matches,
        "pending_reports": pending_reports,
        "registrations_today": registrations_today,
        "top_cities": top_cities,
    }


async def count_pending_reports() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM reports WHERE status = 'pending'"
        ) as cur:
            return (await cur.fetchone())[0]


async def get_users_page(page: int = 0, per_page: int = 10) -> tuple[list[dict], int]:
    offset = page * per_page
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total = (await cur.fetchone())[0]

        async with db.execute(
            """SELECT user_id, name, age, city, username, created_at,
                      is_banned, is_shadow_banned, is_active
               FROM users
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (per_page, offset),
        ) as cur:
            users = [dict(row) for row in await cur.fetchall()]

    return users, total


async def search_users(query: str, limit: int = 10) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if query.isdigit():
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (int(query),)
            ) as cur:
                row = await cur.fetchone()
                return [dict(row)] if row else []

        if query.startswith("@"):
            username = query[1:].lower()
            async with db.execute(
                """SELECT * FROM users
                   WHERE LOWER(username) = ?
                   LIMIT ?""",
                (username, limit),
            ) as cur:
                return [dict(row) for row in await cur.fetchall()]

        pattern = f"%{query}%"
        async with db.execute(
            """SELECT * FROM users
               WHERE name LIKE ? COLLATE NOCASE
                  OR city LIKE ? COLLATE NOCASE
               ORDER BY created_at DESC
               LIMIT ?""",
            (pattern, pattern, limit),
        ) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def get_user_admin_stats(user_id: int) -> dict | None:
    user = await get_user(user_id)
    if not user:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM likes WHERE from_user_id = ?", (user_id,)
        ) as cur:
            likes_given = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM likes WHERE to_user_id = ?", (user_id,)
        ) as cur:
            likes_received = (await cur.fetchone())[0]

        async with db.execute(
            """SELECT COUNT(*) FROM matches
               WHERE user1_id = ? OR user2_id = ?""",
            (user_id, user_id),
        ) as cur:
            matches_count = (await cur.fetchone())[0]

    return {
        "user": user,
        "likes_given": likes_given,
        "likes_received": likes_received,
        "matches_count": matches_count,
        "views_count": user["views_count"],
    }


async def get_pending_reports(page: int = 0, per_page: int = 5) -> tuple[list[dict], int]:
    offset = page * per_page
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT COUNT(*) FROM reports WHERE status = 'pending'"
        ) as cur:
            total = (await cur.fetchone())[0]

        async with db.execute(
            """SELECT r.*,
                      ru.name AS reporter_name,
                      ru.username AS reporter_username,
                      tu.name AS reported_name,
                      tu.username AS reported_username
               FROM reports r
               LEFT JOIN users ru ON ru.user_id = r.reporter_id
               LEFT JOIN users tu ON tu.user_id = r.reported_id
               WHERE r.status = 'pending'
               ORDER BY r.created_at DESC
               LIMIT ? OFFSET ?""",
            (per_page, offset),
        ) as cur:
            reports = [dict(row) for row in await cur.fetchall()]

    return reports, total


async def get_report(report_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT r.*,
                      ru.name AS reporter_name,
                      tu.name AS reported_name
               FROM reports r
               LEFT JOIN users ru ON ru.user_id = r.reporter_id
               LEFT JOIN users tu ON tu.user_id = r.reported_id
               WHERE r.id = ?""",
            (report_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_report_status(report_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reports SET status = ? WHERE id = ?",
            (status, report_id),
        )
        await db.commit()


async def get_broadcast_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT user_id FROM users
               WHERE is_banned = 0 AND is_active = 1"""
        ) as cur:
            rows = await cur.fetchall()
            return [row[0] for row in rows]

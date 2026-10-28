import os
import sqlite3
import re
import unicodedata
import json
import urllib.request
from datetime import datetime, timedelta, date, timezone
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from themes import THEMES_CATALOG, get_theme_for_date, get_theme_by_key

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

def get_vn_now():
    """Lấy thời điểm hiện tại chính xác theo giờ Việt Nam (UTC+7)"""
    return datetime.now(VN_TZ)

def get_vn_today():
    """Lấy ngày hôm nay chính xác theo giờ Việt Nam (UTC+7)"""
    return get_vn_now().date()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, 'duty_schedule.db')

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
app.secret_key = 'tranbinhauto_secret_key_duty_schedule_2026'

# Mật khẩu quản trị Admin
ADMIN_PASSWORD = '196793'

def is_admin():
    """Kiểm tra xem người dùng hiện tại có đang đăng nhập quyền Admin không"""
    return session.get('is_admin') is True

def get_current_theme():
    """
    Xác định theme hiện hành:
    - 1. Chỉ Admin mới có quyền xem thử/đổi giao diện qua ?theme=... hoặc session.
    - 2. Người dùng thông thường và khách luôn xem theme tự động theo thời gian thực (Giờ VN).
    """
    if is_admin():
        theme_arg = request.args.get('theme')
        if theme_arg == 'reset':
            session.pop('active_theme', None)
        elif theme_arg and theme_arg in THEMES_CATALOG:
            session['active_theme'] = theme_arg
            return THEMES_CATALOG[theme_arg]

        active_key = session.get('active_theme')
        if active_key and active_key in THEMES_CATALOG:
            return THEMES_CATALOG[active_key]

    vn_today = get_vn_today()
    return get_theme_for_date(vn_today)

@app.context_processor
def inject_theme():
    """Tự động truyền theme và danh mục all_themes vào tất cả template HTML"""
    current_theme = get_current_theme()
    return dict(theme=current_theme, all_themes=THEMES_CATALOG)


# 8 người cố định trực nhật vệ sinh 7h30 sáng
DUTY_MEMBERS = ['Vinh', 'Dĩ', 'Ân', 'Bảo', 'Nguyên', 'Lợi', 'Thái', 'Duy']
# 2 nhân viên tại Trần Bình Auto không trực nhật nhưng vẫn báo xin nghỉ bình thường
NON_DUTY_STAFF = ['Bảo Mập', 'Phát']
# Danh sách tất cả 10 nhân sự tại Trần Bình Auto
ALL_STAFF = DUTY_MEMBERS + NON_DUTY_STAFF

# Mốc bắt đầu gốc: Nguyên (index 4) trực ngày 16/10/2026
MEMBERS = DUTY_MEMBERS
BASE_DATE = date(2026, 10, 16)
BASE_INDEX = 4  # 0: Vinh, 1: Dĩ, 2: Ân, 3: Bảo, 4: Nguyên, 5: Lợi, 6: Thái, 7: Duy

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        # Bảng lưu ngày tiệm đóng cửa / nghỉ lễ
        conn.execute('''
            CREATE TABLE IF NOT EXISTS shop_holidays (
                holiday_date TEXT PRIMARY KEY,
                reason TEXT
            )
        ''')
        # Bảng lưu các ca nghỉ hiện hành (từ hôm nay trở đi)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS leaves (
                leave_date TEXT,
                member_name TEXT,
                reason TEXT DEFAULT 'Việc cá nhân',
                created_at TEXT,
                PRIMARY KEY (leave_date, member_name)
            )
        ''')
        # Bảng lưu LỊCH SỬ tất cả các ca xin nghỉ
        conn.execute('''
            CREATE TABLE IF NOT EXISTS leaves_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                leave_date TEXT,
                member_name TEXT,
                reason TEXT,
                created_at TEXT,
                archived_at TEXT,
                UNIQUE(leave_date, member_name)
            )
        ''')
        # Bảng lưu mốc xoay tua checkpoint để bảo toàn vòng lặp 8 người khi lưu trữ ca nghỉ cũ
        conn.execute('''
            CREATE TABLE IF NOT EXISTS rotation_checkpoint (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                checkpoint_date TEXT,
                next_cycle_index INTEGER
            )
        ''')
        # Bảng lưu NHẬT KÝ VẾT (Audit Log) theo dõi mọi hành động xin nghỉ, sửa, xóa
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT,
                actor TEXT,
                description TEXT,
                created_at TEXT
            )
        ''')
        # Kiểm tra và thêm cột nếu cơ sở dữ liệu cũ chưa có
        cursor = conn.execute("PRAGMA table_info(leaves)")
        columns = [row['name'] for row in cursor.fetchall()]
        if 'reason' not in columns:
            conn.execute("ALTER TABLE leaves ADD COLUMN reason TEXT DEFAULT 'Việc cá nhân'")
        if 'created_at' not in columns:
            conn.execute("ALTER TABLE leaves ADD COLUMN created_at TEXT")
        conn.commit()

init_db()

def log_action(action_type, description, actor=None):
    """Ghi vết mọi thao tác vào bảng audit_logs để Admin tra cứu"""
    if actor is None:
        actor = 'Admin' if is_admin() else 'Nhân viên'
    timestamp = get_vn_now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with get_db() as conn:
            conn.execute('''
                INSERT INTO audit_logs (action_type, actor, description, created_at)
                VALUES (?, ?, ?, ?)
            ''', (action_type, actor, description, timestamp))
            conn.commit()
    except Exception:
        pass

def cleanup_and_advance_checkpoint():
    """
    Cập nhật mốc xoay tua lịch trực tới ngày hôm nay (giờ VN), tự động chuyển các ca nghỉ đã qua ngày vào
    bảng LỊCH SỬ (leaves_history) và xóa khỏi bảng hiện hành để tránh rối mắt.
    """
    today = get_vn_today()
    today_str = today.strftime('%Y-%m-%d')
    vn_now_str = get_vn_now().strftime('%Y-%m-%d %H:%M:%S')
    
    with get_db() as conn:
        row = conn.execute('SELECT checkpoint_date, next_cycle_index FROM rotation_checkpoint WHERE id = 1').fetchone()
        if not row:
            ckpt_date = BASE_DATE
            cycle_idx = BASE_INDEX
            conn.execute('INSERT INTO rotation_checkpoint (id, checkpoint_date, next_cycle_index) VALUES (1, ?, ?)',
                         (ckpt_date.strftime('%Y-%m-%d'), cycle_idx))
            conn.commit()
        else:
            try:
                ckpt_date = datetime.strptime(row['checkpoint_date'], '%Y-%m-%d').date()
            except Exception:
                ckpt_date = BASE_DATE
            cycle_idx = row['next_cycle_index']

        # Nếu checkpoint trước hôm nay, ta cuốn chiếu qua các ngày quá khứ để chốt ca trực
        if ckpt_date < today:
            holidays = {r['holiday_date']: r['reason'] for r in conn.execute('SELECT * FROM shop_holidays')}
            leaves_data = conn.execute('SELECT leave_date, member_name FROM leaves WHERE leave_date < ? ORDER BY rowid ASC', (today_str,)).fetchall()
            past_leaves = {}
            for r in leaves_data:
                past_leaves.setdefault(r['leave_date'], []).append(r['member_name'])

            days_diff = (today - ckpt_date).days
            for i in range(days_diff):
                d = ckpt_date + timedelta(days=i)
                d_str = d.strftime('%Y-%m-%d')
                
                # Ngày tiệm nghỉ: tạm dừng xoay tua
                if d_str in holidays:
                    continue
                    
                # Ngày làm việc: tìm người tiếp theo trong 8 người trực nhật không xin nghỉ
                day_leave_names = past_leaves.get(d_str, [])
                for _ in range(len(DUTY_MEMBERS)):
                    candidate = DUTY_MEMBERS[cycle_idx % len(DUTY_MEMBERS)]
                    cycle_idx += 1
                    if candidate not in day_leave_names:
                        break

            # Cập nhật checkpoint lên ngày hôm nay
            conn.execute('UPDATE rotation_checkpoint SET checkpoint_date = ?, next_cycle_index = ? WHERE id = 1',
                         (today_str, cycle_idx))

        # 1. TỰ ĐỘNG CHUYỂN CÁC CA NGHỈ ĐÃ QUA NGÀY VÀO BẢNG LỊCH SỬ NGHỈ
        conn.execute('''
            INSERT OR IGNORE INTO leaves_history (leave_date, member_name, reason, created_at, archived_at)
            SELECT leave_date, member_name, reason, created_at, ?
            FROM leaves
            WHERE leave_date < ?
        ''', (vn_now_str, today_str))

        # 2. XÓA KHỎI BẢNG HIỆN HÀNH ĐỂ KHÔNG BỊ RỐI MẮT
        conn.execute('DELETE FROM leaves WHERE leave_date < ?', (today_str,))
        conn.commit()

def get_current_checkpoint():
    with get_db() as conn:
        row = conn.execute('SELECT checkpoint_date, next_cycle_index FROM rotation_checkpoint WHERE id = 1').fetchone()
        if row:
            try:
                ckpt_date = datetime.strptime(row['checkpoint_date'], '%Y-%m-%d').date()
                return ckpt_date, row['next_cycle_index']
            except Exception:
                pass
    return BASE_DATE, BASE_INDEX

def get_schedule(days_ahead=21):
    """Tính toán lịch trực cho n ngày tới tính từ hôm nay cho 8 người trực nhật"""
    today = get_vn_today()
    start_date, start_cycle_index = get_current_checkpoint()
    
    with get_db() as conn:
        holidays = {row['holiday_date']: row['reason'] for row in conn.execute('SELECT * FROM shop_holidays')}
        leaves_data = conn.execute('SELECT rowid, leave_date, member_name, reason, created_at FROM leaves ORDER BY rowid ASC').fetchall()
        leaves_map = {}
        for row in leaves_data:
            leaves_map.setdefault(row['leave_date'], []).append({
                'member_name': row['member_name'],
                'reason': row['reason'] or 'Việc cá nhân',
                'created_at': row['created_at'] or '',
                'rowid': row['rowid'],
                'is_duty_member': row['member_name'] in DUTY_MEMBERS
            })

    schedule = []
    current_cycle_index = start_cycle_index
    
    # Tính toán từ start_date đến ngày cuối cùng của khung hiển thị
    total_days = (today + timedelta(days=days_ahead) - start_date).days + 1
    
    for i in range(total_days):
        check_date = start_date + timedelta(days=i)
        check_date_str = check_date.strftime('%Y-%m-%d')
        
        # 1. Nếu ngày đó tiệm nghỉ: tạm dừng xoay tua, không mất lượt
        if check_date_str in holidays:
            if check_date >= today:
                schedule.append({
                    'date_str': check_date_str,
                    'display_date': check_date.strftime('%d/%m/%Y'),
                    'weekday': check_date.strftime('%A'),
                    'assigned': None,
                    'is_holiday': True,
                    'holiday_reason': holidays[check_date_str],
                    'leaves': [],
                    'skipped_for_duty': []
                })
            continue
            
        # 2. Ngày làm việc: tìm người tiếp theo trong 8 người trực nhật không xin nghỉ
        day_leaves = leaves_map.get(check_date_str, [])
        for idx, item in enumerate(day_leaves):
            item['is_first'] = (idx == 0)
            item['order_idx'] = idx

        day_leave_names = [item['member_name'] for item in day_leaves]
        assigned_person = None
        skipped_for_duty = []
        
        # Xoay tua trong 8 người trực nhật
        for _ in range(len(DUTY_MEMBERS)):
            candidate = DUTY_MEMBERS[current_cycle_index % len(DUTY_MEMBERS)]
            current_cycle_index += 1
            if candidate not in day_leave_names:
                assigned_person = candidate
                break
            else:
                # Tìm lý do của người bị đôn
                r_reason = next((l['reason'] for l in day_leaves if l['member_name'] == candidate), 'Xin nghỉ')
                skipped_for_duty.append({
                    'member_name': candidate,
                    'reason': r_reason
                })
                
        if check_date >= today:
            schedule.append({
                'date_str': check_date_str,
                'display_date': check_date.strftime('%d/%m/%Y'),
                'weekday': check_date.strftime('%A'),
                'assigned': assigned_person,
                'is_holiday': False,
                'holiday_reason': None,
                'leaves': day_leaves,
                'skipped_for_duty': skipped_for_duty
            })
            
    return schedule

def get_leaves_summary(schedule):
    """Lấy danh sách các ca xin nghỉ hiện hành (từ hôm nay trở đi) kèm thông tin ưu tiên nộp trước"""
    today = get_vn_today()
    today_str = today.strftime('%Y-%m-%d')
    with get_db() as conn:
        rows = conn.execute('''
            SELECT rowid, leave_date, member_name, reason, created_at 
            FROM leaves 
            WHERE leave_date >= ?
            ORDER BY leave_date ASC, rowid ASC
        ''', (today_str,)).fetchall()
    
    # Bản đồ kiểm tra ai trùng ngày trực và bị đôn ca
    duty_skip_map = {}
    for s in schedule:
        for skipped in s.get('skipped_for_duty', []):
            duty_skip_map[(s['date_str'], skipped['member_name'])] = s['assigned']
            
    date_map = {}
    for r in rows:
        d = r['leave_date']
        date_map.setdefault(d, []).append(r)
        
    leaves_list = []
    weekday_vn = {
        'Monday': 'Thứ Hai', 'Tuesday': 'Thứ Ba', 'Wednesday': 'Thứ Tư',
        'Thursday': 'Thứ Năm', 'Friday': 'Thứ Sáu', 'Saturday': 'Thứ Bảy', 'Sunday': 'Chủ Nhật'
    }
    
    for r in rows:
        d_str = r['leave_date']
        try:
            d_obj = datetime.strptime(d_str, '%Y-%m-%d').date()
            display_date = d_obj.strftime('%d/%m/%Y')
            weekday_str = weekday_vn.get(d_obj.strftime('%A'), d_obj.strftime('%A'))
        except Exception:
            display_date = d_str
            weekday_str = ''

        raw_created = r['created_at'] or ''
        created_display = raw_created
        try:
            dt_c = datetime.strptime(raw_created, '%Y-%m-%d %H:%M:%S')
            created_display = dt_c.strftime('%H:%M %d/%m')
        except Exception:
            try:
                dt_c2 = datetime.strptime(raw_created, '%d/%m/%Y %H:%M')
                created_display = dt_c2.strftime('%H:%M %d/%m')
            except Exception:
                pass
            
        same_date_all = date_map.get(d_str, [])
        order_idx = next((i for i, item in enumerate(same_date_all) if item['member_name'] == r['member_name']), 0)
        is_first = (order_idx == 0)
        has_conflict = (len(same_date_all) > 1)
        
        earlier_applicants = same_date_all[:order_idx]
        earlier_names = [item['member_name'] for item in earlier_applicants]
        earlier_names_str = ', '.join(earlier_names)
        
        later_applicants = same_date_all[order_idx + 1:]
        later_names = [item['member_name'] for item in later_applicants]
        later_names_str = ', '.join(later_names)
        
        other_names = [item['member_name'] for item in same_date_all if item['member_name'] != r['member_name']]
        
        is_duty_member = (r['member_name'] in DUTY_MEMBERS)
        replacement = duty_skip_map.get((d_str, r['member_name']))

        # Tính toán quyền hủy trong 15 phút
        can_cancel = False
        minutes_left = 0
        now_dt = get_vn_now()
        if is_admin():
            can_cancel = True
        elif raw_created:
            try:
                # Gán múi giờ VN để trừ chênh lệch thời gian chính xác
                c_dt = datetime.strptime(raw_created, '%Y-%m-%d %H:%M:%S').replace(tzinfo=VN_TZ)
                diff_sec = (now_dt - c_dt).total_seconds()
                if 0 <= diff_sec <= 900:  # 15 phút = 900 giây
                    can_cancel = True
                    minutes_left = max(1, int((900 - diff_sec) // 60))
            except Exception:
                pass
        
        leaves_list.append({
            'rowid': r['rowid'],
            'leave_date': d_str,
            'display_date': display_date,
            'weekday_vn': weekday_str,
            'member_name': r['member_name'],
            'reason': r['reason'] or 'Việc cá nhân',
            'created_at': created_display,
            'is_duty_member': is_duty_member,
            'has_conflict': has_conflict,
            'is_first': is_first,
            'order_idx': order_idx,
            'earlier_names_str': earlier_names_str,
            'later_names_str': later_names_str,
            'conflict_with': ', '.join(other_names),
            'conflict_count': len(same_date_all),
            'is_duty_skip': bool(replacement),
            'replaced_by': replacement,
            'is_past': False,
            'can_cancel': can_cancel,
            'minutes_left': minutes_left
        })
        
    return leaves_list

@app.route('/')
def index():
    cleanup_and_advance_checkpoint()
    active_tab = request.args.get('tab', 'schedule')
    schedule = get_schedule(days_ahead=21)
    today_duty = schedule[0] if len(schedule) > 0 else None
    tomorrow_duty = schedule[1] if len(schedule) > 1 else None
    
    weekday_vn = {
        'Monday': 'Thứ Hai', 'Tuesday': 'Thứ Ba', 'Wednesday': 'Thứ Tư',
        'Thursday': 'Thứ Năm', 'Friday': 'Thứ Sáu', 'Saturday': 'Thứ Bảy', 'Sunday': 'Chủ Nhật'
    }
    
    for item in schedule:
        item['weekday_vn'] = weekday_vn.get(item['weekday'], item['weekday'])

    leaves_summary = get_leaves_summary(schedule)
    
    leaves_by_date = {}
    for item in leaves_summary:
        leaves_by_date.setdefault(item['leave_date'], []).append({
            'member_name': item['member_name'],
            'reason': item['reason'],
            'created_at': item['created_at'],
            'is_first': item['is_first'],
            'order_idx': item['order_idx'],
            'is_duty_member': item['is_duty_member']
        })
        
    duty_by_date = {s['date_str']: s['assigned'] for s in schedule if not s.get('is_holiday')}
    has_any_conflict = any(l['has_conflict'] for l in leaves_summary)

    today_dt = get_vn_today()
    today_str = today_dt.strftime('%Y-%m-%d')
    today_leaves = [item for item in leaves_summary if item['leave_date'] == today_str]

    # Quy định: Không cho xin nghỉ Hôm nay và Ngày mai (Được phép từ Ngày mốt - cách 2 ngày trở đi)
    min_leave_date = today_dt + timedelta(days=2)
    min_leave_date_str = min_leave_date.strftime('%Y-%m-%d')
    min_leave_date_display = min_leave_date.strftime('%d/%m/%Y')

    with get_db() as conn:
        holidays_list = conn.execute('SELECT holiday_date, reason FROM shop_holidays ORDER BY holiday_date ASC').fetchall()

    return render_template('index.html', 
                           active_tab=active_tab,
                           today_duty=today_duty, 
                           tomorrow_duty=tomorrow_duty, 
                           schedule=schedule,
                           duty_members=DUTY_MEMBERS,
                           non_duty_staff=NON_DUTY_STAFF,
                           all_staff=ALL_STAFF,
                           leaves_summary=leaves_summary,
                           leaves_by_date=leaves_by_date,
                           duty_by_date=duty_by_date,
                           future_leaves_count=len(leaves_summary),
                           has_any_conflict=has_any_conflict,
                           today_leaves=today_leaves,
                           today_date_str=today_str,
                           min_leave_date_str=min_leave_date_str,
                           min_leave_date_display=min_leave_date_display,
                           holidays_list=holidays_list,
                           is_admin=is_admin())

def get_leave_cycle(d):
    """
    Quy định chu kỳ tháng của ca nghỉ:
    - Bắt đầu từ ngày 8 tháng trước đến hết ngày 7 tháng này.
    Trả về: (cycle_key, cycle_label, start_date, end_date)
    """
    if d.day >= 8:
        start_d = date(d.year, d.month, 8)
        if d.month == 12:
            end_d = date(d.year + 1, 1, 7)
            cycle_key = f"{d.year}-12"
        else:
            end_d = date(d.year, d.month + 1, 7)
            cycle_key = f"{d.year}-{d.month:02d}"
    else:
        if d.month == 1:
            start_d = date(d.year - 1, 12, 8)
            end_d = date(d.year, 1, 7)
            cycle_key = f"{d.year-1}-12"
        else:
            start_d = date(d.year, d.month - 1, 8)
            end_d = date(d.year, d.month, 7)
            cycle_key = f"{d.year}-{d.month-1:02d}"

    cycle_label = f"Kỳ {start_d.strftime('%d/%m')} - {end_d.strftime('%d/%m/%Y')}"
    return cycle_key, cycle_label, start_d, end_d

def get_current_view_cycle(today):
    """
    Quy định hiển thị bảng cho nhân viên:
    - Đến ngày 7 là hết tháng làm việc.
    - Trong ngày 7 và cả ngày 8: Nhân viên vẫn được xem bảng ngày nghỉ của kỳ vừa rồi để đối soát, phản ánh nếu có sai sót.
    - Sang 00:00 ngày 9: Bảng của kỳ cũ chính thức khép lại và ẩn đi đối với nhân viên thường (chỉ Admin mới xem lại được),
      và bảng của nhân viên tự động làm mới (reset về 0 ngày nghỉ) để tích lũy cho chu kỳ mới!
    """
    if today.day <= 8:
        # Vẫn xem kỳ kết thúc vào ngày 7 tháng này
        if today.month == 1:
            start_d = date(today.year - 1, 12, 8)
            end_d = date(today.year, 1, 7)
            cycle_key = f"{today.year-1}-12"
        else:
            start_d = date(today.year, today.month - 1, 8)
            end_d = date(today.year, today.month, 7)
            cycle_key = f"{today.year}-{today.month-1:02d}"
    else:
        # Từ ngày 9 trở đi: Sang chu kỳ mới bắt đầu từ ngày 8 tháng này
        start_d = date(today.year, today.month, 8)
        if today.month == 12:
            end_d = date(today.year + 1, 1, 7)
            cycle_key = f"{today.year}-12"
        else:
            end_d = date(today.year, today.month + 1, 7)
            cycle_key = f"{today.year}-{today.month:02d}"

    cycle_label = f"Kỳ {start_d.strftime('%d/%m')} - {end_d.strftime('%d/%m/%Y')}"
    return cycle_key, cycle_label, start_d, end_d

@app.route('/history')
def history():
    """Trang tra cứu lịch sử xin nghỉ theo chu kỳ Trần Bình Auto (reset vào 00:00 ngày 9)"""
    cleanup_and_advance_checkpoint()
    
    today = get_vn_today()
    today_str = today.strftime('%Y-%m-%d')
    curr_cycle_key, curr_cycle_label, curr_start_d, curr_end_d = get_current_view_cycle(today)

    admin_logged_in = is_admin()

    # QUY ĐỊNH PHÂN QUYỀN:
    # - Nhân viên thường: BẮT BUỘC chỉ xem Kỳ hiển thị hiện hành (ngày 7 & 8 vẫn xem kỳ vừa rồi, 00:00 ngày 9 mới reset kỳ mới).
    # - Chỉ Admin: Mới được quyền chọn các kỳ cũ hoặc xem toàn bộ lịch sử ('all').
    selected_cycle = request.args.get('cycle')
    if not admin_logged_in or selected_cycle is None:
        selected_cycle = curr_cycle_key

    selected_member = request.args.get('member', '').strip()
    
    with get_db() as conn:
        rows = conn.execute('''
            SELECT id, leave_date, member_name, reason, created_at, 'history' as source
            FROM leaves_history
            UNION ALL
            SELECT rowid as id, leave_date, member_name, reason, created_at, 'active' as source
            FROM leaves
            ORDER BY leave_date DESC, id DESC
        ''').fetchall()
        
    weekday_vn = {
        'Monday': 'Thứ Hai', 'Tuesday': 'Thứ Ba', 'Wednesday': 'Thứ Tư',
        'Thursday': 'Thứ Năm', 'Friday': 'Thứ Sáu', 'Saturday': 'Thứ Bảy', 'Sunday': 'Chủ Nhật'
    }
    
    cycles_dict = {
        curr_cycle_key: {
            'key': curr_cycle_key,
            'label': curr_cycle_label,
            'start_date': curr_start_d,
            'end_date': curr_end_d,
            'is_current': True
        }
    }
    history_list = []
    
    for r in rows:
        d_str = r['leave_date']
        try:
            d_obj = datetime.strptime(d_str, '%Y-%m-%d').date()
            display_date = d_obj.strftime('%d/%m/%Y')
            weekday_str = weekday_vn.get(d_obj.strftime('%A'), d_obj.strftime('%A'))
            is_past = (d_str < today_str)
            c_key, c_label, c_start, c_end = get_leave_cycle(d_obj)
        except Exception:
            d_obj = today
            display_date = d_str
            weekday_str = ''
            is_past = False
            c_key, c_label, c_start, c_end = curr_cycle_key, curr_cycle_label, curr_start_d, curr_end_d

        if c_key not in cycles_dict:
            cycles_dict[c_key] = {
                'key': c_key,
                'label': c_label,
                'start_date': c_start,
                'end_date': c_end,
                'is_current': (c_key == curr_cycle_key)
            }
        
        # Lọc theo kỳ
        if selected_cycle != 'all' and c_key != selected_cycle:
            continue
            
        # Lọc theo nhân viên
        if selected_member and r['member_name'] != selected_member:
            continue
            
        raw_created = r['created_at'] or ''
        created_display = raw_created
        try:
            dt_c = datetime.strptime(raw_created, '%Y-%m-%d %H:%M:%S')
            created_display = dt_c.strftime('%H:%M %d/%m/%Y')
        except Exception:
            pass

        is_duty_staff = (r['member_name'] in DUTY_MEMBERS)
        
        # Kiểm tra điều kiện hủy (trong 15 phút kể từ lúc nộp hoặc là Admin)
        can_cancel = False
        minutes_left = 0
        now_dt = get_vn_now()
        if is_admin():
            can_cancel = True
        elif not is_past and r['source'] == 'active' and raw_created:
            try:
                c_dt = datetime.strptime(raw_created, '%Y-%m-%d %H:%M:%S').replace(tzinfo=VN_TZ)
                diff_sec = (now_dt - c_dt).total_seconds()
                if 0 <= diff_sec <= 900:  # 15 phút
                    can_cancel = True
                    minutes_left = max(1, int((900 - diff_sec) // 60))
            except Exception:
                pass
        
        history_list.append({
            'id': r['id'],
            'leave_date': d_str,
            'display_date': display_date,
            'weekday_vn': weekday_str,
            'cycle_key': c_key,
            'cycle_label': c_label,
            'member_name': r['member_name'],
            'reason': r['reason'] or 'Việc cá nhân',
            'created_at': created_display,
            'is_duty_staff': is_duty_staff,
            'is_past': is_past,
            'source': r['source'],
            'can_cancel': can_cancel,
            'minutes_left': minutes_left
        })
        
    # Sắp xếp các chu kỳ theo ngày bắt đầu giảm dần (mới nhất lên đầu)
    sorted_cycles = sorted(cycles_dict.values(), key=lambda c: c['start_date'], reverse=True)
    past_cycles = [c for c in sorted_cycles if not c['is_current']]

    # Xác định nhãn kỳ đang hiển thị
    if selected_cycle == 'all':
        active_cycle_label = "Toàn Bộ Lịch Sử (Tất cả thời gian)"
    elif selected_cycle in cycles_dict:
        active_cycle_label = cycles_dict[selected_cycle]['label']
    else:
        active_cycle_label = curr_cycle_label

    # Thống kê số ngày nghỉ theo từng nhân sự trong chu kỳ / khoảng thời gian đã chọn
    stats_by_member = {}
    for staff in ALL_STAFF:
        count = sum(1 for item in history_list if item['member_name'] == staff)
        stats_by_member[staff] = count

    # Nếu là Admin, lấy danh sách nhật ký vết (Audit Logs) 50 hành động gần nhất
    audit_logs = []
    if is_admin():
        with get_db() as conn:
            audit_logs = conn.execute('''
                SELECT id, action_type, actor, description, created_at
                FROM audit_logs
                ORDER BY id DESC LIMIT 50
            ''').fetchall()

    return render_template('history.html',
                           history_list=history_list,
                           selected_cycle=selected_cycle,
                           selected_member=selected_member,
                           curr_cycle_key=curr_cycle_key,
                           curr_cycle_label=curr_cycle_label,
                           active_cycle_label=active_cycle_label,
                           past_cycles=past_cycles,
                           all_staff=ALL_STAFF,
                           duty_members=DUTY_MEMBERS,
                           non_duty_staff=NON_DUTY_STAFF,
                           stats_by_member=stats_by_member,
                           total_leaves=len(history_list),
                           is_admin=is_admin(),
                           is_review_phase=(today.day in [7, 8]),
                           review_day=today.day,
                           audit_logs=audit_logs)

@app.route('/admin-login', methods=['POST'])
def admin_login():
    """Đăng nhập chế độ Admin quản trị tối cao"""
    password = request.form.get('password', '').strip()
    next_url = request.form.get('next_url') or request.referrer or url_for('index')
    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
    return redirect(next_url)

@app.route('/admin-logout', methods=['POST', 'GET'])
def admin_logout():
    """Thoát chế độ Admin quản trị"""
    session.pop('is_admin', None)
    session.pop('active_theme', None)
    return redirect(request.referrer or url_for('index'))

@app.route('/edit-leave', methods=['POST'])
def edit_leave():
    """Admin chỉnh sửa thông tin ca xin nghỉ (Ghi nhật ký vết)"""
    if not is_admin():
        return redirect(request.referrer or url_for('index'))
        
    source = request.form.get('source')
    record_id = request.form.get('id')
    old_date = request.form.get('old_leave_date')
    old_member = request.form.get('old_member_name')
    new_date = request.form.get('new_leave_date')
    new_member = request.form.get('new_member_name')
    new_reason = request.form.get('new_reason', '').strip() or 'Việc cá nhân'
    
    if new_date and new_member:
        with get_db() as conn:
            if source == 'history' and record_id:
                conn.execute('''
                    UPDATE leaves_history 
                    SET leave_date = ?, member_name = ?, reason = ?
                    WHERE id = ?
                ''', (new_date, new_member, new_reason, record_id))
                conn.commit()
                log_action('SỬA ĐƠN', f"Admin sửa ca lịch sử của {old_member} (ngày {old_date}) ➔ {new_member} (ngày {new_date}, lý do: '{new_reason}')", actor='Admin')
            elif source == 'active' and old_date and old_member:
                conn.execute('''
                    UPDATE leaves 
                    SET leave_date = ?, member_name = ?, reason = ?
                    WHERE leave_date = ? AND member_name = ?
                ''', (new_date, new_member, new_reason, old_date, old_member))
                conn.commit()
                log_action('SỬA ĐƠN', f"Admin sửa ca sắp tới của {old_member} (ngày {old_date}) ➔ {new_member} (ngày {new_date}, lý do: '{new_reason}')", actor='Admin')
                
    return redirect(request.referrer or url_for('index'))

@app.route('/delete-history', methods=['POST'])
def delete_history():
    """
    Quy định xóa từ trang Lịch Sử Nghỉ:
    - Nếu là Admin: Có quyền xóa bất kỳ lúc nào (ghi nhận vết xóa).
    - Nếu là nhân viên: Chỉ được hủy trong vòng 15 phút sau khi nộp (nếu quá 15 phút, từ chối và ghi vết cảnh báo).
    """
    record_id = request.form.get('id')
    source = request.form.get('source')
    leave_date = request.form.get('leave_date')
    member_name = request.form.get('member_name')
    today_str = get_vn_today().strftime('%Y-%m-%d')
    admin_mode = is_admin()
    
    with get_db() as conn:
        if admin_mode:
            if source == 'history' and record_id:
                conn.execute('DELETE FROM leaves_history WHERE id = ?', (record_id,))
                conn.commit()
                log_action('XÓA LỊCH SỬ', f"Admin đã xóa vĩnh viễn ca nghỉ ngày {leave_date} của {member_name} trong lịch sử", actor='Admin')
            elif leave_date and member_name:
                conn.execute('DELETE FROM leaves WHERE leave_date = ? AND member_name = ?', (leave_date, member_name))
                conn.commit()
                log_action('XÓA ĐƠN', f"Admin đã xóa ca nghỉ ngày {leave_date} của {member_name}", actor='Admin')
        else:
            # Nhân viên: Kiểm tra giới hạn 15 phút
            if source == 'active' and leave_date and leave_date >= today_str and member_name:
                row = conn.execute('SELECT created_at FROM leaves WHERE leave_date = ? AND member_name = ?', (leave_date, member_name)).fetchone()
                if row and row['created_at']:
                    try:
                        c_dt = datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=VN_TZ)
                        diff_sec = (get_vn_now() - c_dt).total_seconds()
                        if diff_sec <= 900:  # Trong vòng 15 phút
                            conn.execute('DELETE FROM leaves WHERE leave_date = ? AND member_name = ?', (leave_date, member_name))
                            conn.commit()
                            log_action('HỦY ĐƠN (15P)', f"{member_name} tự hủy đơn nghỉ ngày {leave_date} (trong hạn 15 phút)", actor=member_name)
                        else:
                            log_action('HỦY THẤT BẠI', f"Cảnh báo: Có người cố hủy đơn nghỉ ngày {leave_date} của {member_name} sau khi đã quá hạn 15 phút", actor='Nhân viên')
                    except Exception:
                        pass
            
    return redirect(request.referrer or url_for('history'))

# ═══════════════════════════════════════════════════════════════════
# TRỢ LÝ ẢO AI (GOOGLE GEMINI, OLLAMA & NLP TIẾNG VIỆT TÍCH HỢP)
# ═══════════════════════════════════════════════════════════════════

def load_dotenv():
    """Tự động đọc file .env nếu có để tải các biến môi trường (như GEMINI_API_KEY)"""
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

load_dotenv()

def get_gemini_api_key():
    return os.environ.get('GEMINI_API_KEY', '').strip()

def get_gemini_model():
    return os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash').strip() or 'gemini-1.5-flash'

OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3')

def call_gemini_api(prompt, system_instruction=None, json_mode=False, timeout=5.0):
    """Gọi trực tiếp Google Gemini API qua HTTP REST (không cần thư viện nặng, chạy mượt trên mọi môi trường)"""
    api_key = get_gemini_api_key()
    if not api_key:
        return None
    model = get_gemini_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.1 if json_mode else 0.7,
            "maxOutputTokens": 1000
        }
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res_data = json.loads(resp.read().decode('utf-8'))
            candidates = res_data.get('candidates') or []
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                if parts:
                    return parts[0].get('text', '').strip()
    except Exception:
        pass
    return None

def parse_with_gemini(text, today):
    """Trích xuất người xin nghỉ và ngày nghỉ bằng Google Gemini AI (chính xác tuyệt đối)"""
    if not get_gemini_api_key():
        return None, None, [], None

    prompt = f"""
Bạn là trợ lý AI trích xuất thông tin xin nghỉ việc cho Trần Bình Auto.
Hôm nay là: {today.strftime('%Y-%m-%d')} ({today.strftime('%A')}).
Danh sách 10 nhân sự hợp lệ: {', '.join(ALL_STAFF)}.
Tin nhắn của nhân viên: "{text}"

Yêu cầu: Hãy phân tích và trả về DUY NHẤT một đối tượng JSON:
{{
  "member_name": "Tên chính xác trong danh sách 10 nhân sự hoặc null",
  "leave_dates": ["YYYY-MM-DD", ...],
  "reason": "Lý do xin nghỉ"
}}
QUY TẮC NHẬN DIỆN:
- Nếu xin nghỉ nhiều ngày (ví dụ "ngày mốt", "thứ 7 và chủ nhật tuần sau", "từ 28 đến 30/10"), mảng "leave_dates" PHẢI chứa ĐỦ TẤT CẢ các ngày đó dạng YYYY-MM-DD.
- Nếu không có tên hợp lệ hoặc ngày hợp lệ, trả về null.
"""
    try:
        res = call_gemini_api(prompt, json_mode=True, timeout=4.0)
        if res:
            res_json = json.loads(res)
            m_name = res_json.get('member_name')
            l_dates_raw = res_json.get('leave_dates') or ([res_json.get('leave_date')] if res_json.get('leave_date') else [])
            reason = res_json.get('reason') or 'Việc cá nhân'

            parsed_dates = []
            for ld in l_dates_raw:
                try:
                    parsed_dates.append(datetime.strptime(ld, '%Y-%m-%d').date())
                except Exception:
                    pass

            if m_name in ALL_STAFF and parsed_dates:
                return m_name, parsed_dates[0], parsed_dates, reason
    except Exception:
        pass
    return None, None, [], None

def remove_accents(input_str):
    if not input_str:
        return ''
    nfkd = unicodedata.normalize('NFKD', input_str)
    return ''.join([c for c in nfkd if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')

def parse_with_rule_engine(text, today):
    """Bộ phân tích ngôn ngữ tự nhiên Tiếng Việt tốc độ cao (0ms, không phụ thuộc server ngoài)
    Hỗ trợ:
    - 1 ngày cụ thể (25/10, ngày mai, thứ hai...)
    - Khoảng ngày liên tiếp (từ 20/10 đến 23/10, nghỉ 3 ngày từ ngày mai...)
    - Danh sách nhiều ngày (ngày 20, 22 và 25/10...)
    """
    text_clean = text.strip()
    norm_text = remove_accents(text_clean.lower())
    
    # 1. Tìm nhân viên (ưu tiên tên dài trước ví dụ Bảo Mập trước Bảo)
    found_member = None
    for staff in sorted(ALL_STAFF, key=lambda s: len(s), reverse=True):
        staff_norm = remove_accents(staff.lower())
        if re.search(r'\b' + re.escape(staff_norm) + r'\b', norm_text):
            found_member = staff
            break
            
    # 2. Tìm ngày nghỉ (Trích xuất danh sách ngày: found_dates)
    found_dates = []

    # 2.1. Dạng khoảng ngày liên tiếp: "từ [ngày] D1 [tháng M1] đến [ngày] D2 tháng M2"
    pat_range = r'(?:tu\s*|từ\s*)?(?:ngay\s*)?(\d{1,2})(?:\s*(?:[/\-]|thang\s*|t\s*)(\d{1,2}))?(?:\s*[/\-]\s*|\s*nam\s*)?(\d{4})?\s*(?:den|đến|toi|tới|-)\s*(?:ngay\s*)?(\d{1,2})\s*(?:[/\-]|thang\s*|t\s*)(\d{1,2})(?:\s*[/\-]\s*|\s*nam\s*)?(\d{4})?'
    range_match = re.search(pat_range, norm_text)
    if range_match:
        try:
            d1 = int(range_match.group(1))
            m1 = int(range_match.group(2)) if range_match.group(2) else int(range_match.group(5))
            y1 = int(range_match.group(3)) if range_match.group(3) else today.year
            
            d2 = int(range_match.group(4))
            m2 = int(range_match.group(5))
            y2 = int(range_match.group(6)) if range_match.group(6) else y1
            
            start_d = date(y1, m1, d1)
            end_d = date(y2, m2, d2)
            if start_d > end_d:
                start_d, end_d = end_d, start_d
            
            num_days = (end_d - start_d).days + 1
            if 0 < num_days <= 31:
                found_dates = [start_d + timedelta(days=i) for i in range(num_days)]
        except Exception:
            pass

    # 2.2. Dạng "nghỉ N ngày từ..." (VD: "nghỉ 3 ngày từ 20/10", "nghỉ 3 ngày từ 20 tháng 10", "nghỉ 2 ngày từ ngày mai")
    if not found_dates:
        n_days_match = re.search(r'ngh[i|y]\s*(\d{1,2})\s*ngay\s*(?:lien tiep)?\s*(?:tu|từ|bat dau tu)?\s*(.*)', norm_text)
        if n_days_match:
            try:
                count_days = int(n_days_match.group(1))
                tail = n_days_match.group(2)
                base_d = None
                
                dm = re.search(r'(\d{1,2})\s*(?:[/\-]|thang\s*|t\s*)(\d{1,2})(?:\s*[/\-]\s*|\s*nam\s*)?(\d{4})?', tail)
                if dm:
                    d_val = int(dm.group(1))
                    m_val = int(dm.group(2))
                    y_val = int(dm.group(3)) if dm.group(3) else today.year
                    base_d = date(y_val, m_val, d_val)
                elif re.search(r'\b(ngay mai|mai)\b', tail):
                    base_d = today + timedelta(days=1)
                elif re.search(r'\b(ngay mot|mot)\b', tail):
                    base_d = today + timedelta(days=2)
                elif re.search(r'\b(hom nay|nay)\b', tail):
                    base_d = today

                if base_d and 0 < count_days <= 31:
                    found_dates = [base_d + timedelta(days=i) for i in range(count_days)]
            except Exception:
                pass

    # 2.3. Nhiều ngày DD/MM hoặc DD tháng MM đầy đủ (VD: "20/10 và 25/10", "23/10, 28/10", "20 tháng 10 và 22 tháng 10")
    if not found_dates:
        date_matches = list(re.finditer(r'(\d{1,2})\s*(?:[/\-]|thang\s*|t\s*)(\d{1,2})(?:\s*[/\-]\s*|\s*nam\s*)?(\d{4})?', norm_text))
        if len(date_matches) > 1:
            for dm in date_matches:
                try:
                    d = int(dm.group(1))
                    m_val = int(dm.group(2))
                    y = int(dm.group(3)) if dm.group(3) else today.year
                    if 1 <= d <= 31 and 1 <= m_val <= 12:
                        d_obj = date(y, m_val, d)
                        if d_obj not in found_dates:
                            found_dates.append(d_obj)
                except ValueError:
                    pass

    # 2.4. Dạng nhóm ngày chung tháng (VD: "ngày 28 23 tháng 10", "25 26 tháng 10", "25, 26 tháng 10", "20, 22 và 25/10", "28 và ngày 23/10")
    if not found_dates:
        pat_group = r'((?:\b\d{1,2}\b(?:\s*,\s*|\s+(?:va|voi|va\s+ngay|voi\s+ngay|ngay)?\s*|\s*-\s*))+\b\d{1,2}\b)\s*(?:[/\-]|thang\s*|t\s*)(\d{1,2})(?:\s*[/\-]\s*|\s*nam\s*)?(\d{4})?'
        m_group = re.search(pat_group, norm_text)
        if m_group:
            try:
                days = [int(x) for x in re.findall(r'\b\d{1,2}\b', m_group.group(1)) if 1 <= int(x) <= 31]
                m_val = int(m_group.group(2))
                y = int(m_group.group(3)) if m_group.group(3) else today.year
                if 1 <= m_val <= 12:
                    for d in days:
                        try:
                            d_obj = date(y, m_val, d)
                            if d_obj not in found_dates:
                                found_dates.append(d_obj)
                        except ValueError:
                            pass
            except Exception:
                pass

    if found_dates:
        found_dates = sorted(list(set(found_dates)))

    # 2.5. Xử lý theo THỨ TRONG TUẦN (hỗ trợ nhiều thứ, khoảng từ thứ X đến thứ Y, cuối tuần)
    if not found_dates:
        is_next_week = any(k in norm_text for k in ['tuan sau', 'tuan toi', 'toi', 'sang tuan'])
        curr_monday = today - timedelta(days=today.weekday())
        target_monday = curr_monday + timedelta(days=7 if is_next_week else 0)

        # 2.5.1. Cụm từ "cuối tuần" (Thứ 7 & Chủ Nhật)
        if 'cuoi tuan' in norm_text:
            sat = target_monday + timedelta(days=5)
            sun = target_monday + timedelta(days=6)
            if not is_next_week and sat < today:
                sat += timedelta(days=7)
                sun += timedelta(days=7)
            found_dates = [sat, sun]

        val_map = {
            'thu 2': 0, 'thu2': 0, 'thu hai': 0,
            'thu 3': 1, 'thu3': 1, 'thu ba': 1,
            'thu 4': 2, 'thu4': 2, 'thu tu': 2,
            'thu 5': 3, 'thu5': 3, 'thu nam': 3,
            'thu 6': 4, 'thu6': 4, 'thu sau': 4,
            'thu 7': 5, 'thu7': 5, 'thu bay': 5,
            'chu nhat': 6, 'cn': 6
        }
        pat_w = r'(thu\s*[2-7]|thu\s*hai|thu\s*ba|thu\s*tu|thu\s*nam|thu\s*sau|thu\s*bay|chu\s*nhat|\bcn\b)'

        # 2.5.2. Khoảng "từ thứ X đến/tới thứ Y" (VD: "từ thứ 5 đến thứ 7 tuần sau", "từ thứ 2 tới thứ 4")
        if not found_dates:
            range_w_match = re.search(r'(?:tu|từ)\s*' + pat_w + r'\s*(?:den|đến|toi|tới|-)\s*' + pat_w, norm_text)
            if range_w_match:
                w1_str = re.sub(r'\s+', ' ', range_w_match.group(1).strip())
                w2_str = re.sub(r'\s+', ' ', range_w_match.group(2).strip())
                w1 = val_map.get(w1_str)
                w2 = val_map.get(w2_str)
                if w1 is not None and w2 is not None:
                    if w1 <= w2:
                        days_range = list(range(w1, w2 + 1))
                    else:
                        days_range = list(range(w1, 7)) + list(range(0, w2 + 1))
                    res = [target_monday + timedelta(days=d) for d in days_range]
                    if not is_next_week and any(d < today for d in res):
                        res = [d + timedelta(days=7) for d in res]
                    found_dates = res

        # 2.5.3. Liệt kê một hoặc nhiều thứ (VD: "thứ 7 chủ nhật tuần sau", "thứ 7 và chủ nhật", "thứ 2 và thứ 4 tuần sau")
        if not found_dates:
            matches_w = list(re.finditer(pat_w, norm_text))
            if matches_w:
                w_indices = []
                for mw in matches_w:
                    s_clean = re.sub(r'\s+', ' ', mw.group(1).strip())
                    v = val_map.get(s_clean)
                    if v is not None and v not in w_indices:
                        w_indices.append(v)
                if w_indices:
                    res = []
                    for w in w_indices:
                        d = target_monday + timedelta(days=w)
                        if not is_next_week and d < today:
                            d += timedelta(days=7)
                        res.append(d)
                    # Nếu không nói tuần sau nhưng thứ đầu tiên đã qua thì cả nhóm dời sang tuần sau
                    if not is_next_week and any(d < today for d in res):
                        res = [d + timedelta(days=7) for d in res]
                    found_dates = sorted(list(set(res)))

    # 2.6. Nếu vẫn chưa có danh sách, tìm ngày đơn lẻ dạng DD/MM, DD tháng MM, hoặc hôm nay, ngày mai, ngày mốt
    if not found_dates:
        single_date = None
        # DD/MM hoặc DD tháng MM hoặc DD/MM/YYYY
        m = re.search(r'(?:ngay\s*)?(\d{1,2})\s*(?:[/\-]|thang\s*|t\s*)(\d{1,2})(?:\s*[/\-]\s*|\s*nam\s*)?(\d{4})?', norm_text)
        if m:
            try:
                d = int(m.group(1))
                m_val = int(m.group(2))
                y = int(m.group(3)) if m.group(3) else today.year
                d_obj = date(y, m_val, d)
                if d_obj < today and m_val < today.month:
                    d_obj = date(y + 1, m_val, d)
                single_date = d_obj
            except ValueError:
                pass
                    
        # Từ ngữ tương đối: hôm nay, mai, ngày mốt (hỗ trợ cả kết hợp nhiều ngày liên tiếp)
        if not single_date:
            if re.search(r'\b(tu\s+hom\s+nay\s+(?:den|toi|-)\s*(?:ngay\s*)?mot|hom\s+nay\s*(?:va|,)?\s*(?:ngay\s*)?mai\s*(?:va|,)\s*(?:ngay\s*)?mot)\b', norm_text):
                found_dates = [today, today + timedelta(days=1), today + timedelta(days=2)]
            elif re.search(r'\b(tu\s+hom\s+nay\s+(?:den|toi|-)\s*(?:ngay\s*)?mai|hom\s+nay\s*(?:va|,)\s*(?:ngay\s*)?mai)\b', norm_text):
                found_dates = [today, today + timedelta(days=1)]
            elif re.search(r'\b(tu\s+(?:ngay\s*)?mai\s+(?:den|toi|-)\s*(?:ngay\s*)?mot|(?:ngay\s*)?mai\s*(?:va|,)\s*(?:ngay\s*)?mot)\b', norm_text):
                found_dates = [today + timedelta(days=1), today + timedelta(days=2)]
            elif re.search(r'\b(hom nay|nay|hom ni)\b', norm_text):
                single_date = today
            elif re.search(r'\b(ngay mai|mai)\b', norm_text):
                single_date = today + timedelta(days=1)
            elif re.search(r'\b(ngay mot|mot|ngay kia)\b', norm_text):
                single_date = today + timedelta(days=2)

        if single_date:
            found_dates = [single_date]
            
    # 3. Trích xuất lý do
    found_reason = 'Việc cá nhân'
    kw_map = [
        ('ve que', 'Về quê'),
        ('dam cuoi', 'Đám cưới'),
        ('dam tiec', 'Đám tiệc'),
        ('kham benh', 'Khám bệnh'),
        ('di vien', 'Khám bệnh / Nằm viện'),
        ('gia dinh', 'Việc gia đình'),
        ('du lich', 'Đi du lịch'),
        ('ban viec', 'Bận việc riêng'),
    ]
    for k, v in kw_map:
        if k in norm_text:
            found_reason = v
            break
    else:
        m = re.search(r'(?:ly\s*do|lý\s*do|vì|do|bận|di|đi|nghi\s*de|nghỉ\s*để)\s*[:=]?\s*(.*)', text_clean, re.I)
        if m and m.group(1).strip():
            val = m.group(1).strip(' ,.:;-!?')
            found_reason = val[0].upper() + val[1:]

    first_date = found_dates[0] if found_dates else None
    return found_member, first_date, found_dates, found_reason

_ollama_checked_time = 0
_ollama_available = False

def is_ollama_online():
    """Kiểm tra nhanh xem server Ollama có đang chạy không (cache 30s để tối ưu tốc độ)"""
    global _ollama_checked_time, _ollama_available
    import time
    now = time.time()
    if now - _ollama_checked_time < 30:
        return _ollama_available
    
    _ollama_checked_time = now
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=0.3):
            _ollama_available = True
            return True
    except Exception:
        _ollama_available = False
        return False

def parse_with_ollama(text, today):
    """Gửi yêu cầu tới Ollama nếu service đang hoạt động (hỗ trợ nhiều ngày)"""
    if not is_ollama_online():
        return None, None, [], None

    prompt = f"""
Bạn là trợ lý AI trích xuất thông tin xin nghỉ việc cho Trần Bình Auto.
Hôm nay là: {today.strftime('%Y-%m-%d')} ({today.strftime('%A')}).
Danh sách 10 nhân sự hợp lệ: {', '.join(ALL_STAFF)}.
Tin nhắn của nhân viên: "{text}"

Yêu cầu: Hãy phân tích và trả về DUY NHẤT một đối tượng JSON:
{{
  "member_name": "Tên chính xác trong danh sách 10 nhân sự",
  "leave_dates": ["YYYY-MM-DD", ...],
  "reason": "Lý do xin nghỉ"
}}
QUY TẮC NHẬN DIỆN NHIỀU NGÀY:
- Nếu xin nghỉ nhiều ngày (ví dụ: "thứ 7 chủ nhật tuần sau", "từ thứ 5 đến thứ 7", "cuối tuần sau", "ngày 25 và 26/10"), mảng "leave_dates" PHẢI chứa ĐỦ TẤT CẢ các ngày đó dạng YYYY-MM-DD.
- Ví dụ "thứ 7 chủ nhật tuần sau": phải có 2 ngày là Thứ Bảy và Chủ Nhật của tuần sau.
- Nếu không có tên hợp lệ hoặc ngày hợp lệ, trả về null.
"""
    try:
        req_data = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }).encode('utf-8')
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=req_data,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            res_json = json.loads(data.get('response', '{}'))
            m_name = res_json.get('member_name')
            l_dates_raw = res_json.get('leave_dates') or ([res_json.get('leave_date')] if res_json.get('leave_date') else [])
            reason = res_json.get('reason') or 'Việc cá nhân'
            
            parsed_dates = []
            for ld in l_dates_raw:
                try:
                    parsed_dates.append(datetime.strptime(ld, '%Y-%m-%d').date())
                except Exception:
                    pass

            if m_name in ALL_STAFF and parsed_dates:
                first_d = parsed_dates[0]
                return m_name, first_d, parsed_dates, reason
    except Exception:
        pass
    return None, None, [], None

def ai_parse_message(text):
    """
    Hệ thống kết hợp thông minh 3 tầng (3-Tier Hybrid):
    1. Google Gemini Cloud API (nếu có GEMINI_API_KEY): Siêu tốc, thông minh, hiểu sắc thái tiếng Việt tốt nhất.
    2. Ollama Local LLM: Cho môi trường có GPU / LLM offline.
    3. NLP Tiếng Việt tích hợp sẵn: 0ms, luôn hoạt động offline 100%, không phụ thuộc bất kỳ API nào.
    """
    today = get_vn_today()

    # Tầng 1: Google Gemini Cloud AI
    m_name, first_d, found_dates, reason = parse_with_gemini(text, today)
    if m_name and found_dates:
        return m_name, first_d, found_dates, reason, f"Google Gemini ({get_gemini_model()})"

    # Tầng 2: Ollama Local LLM
    m_name, first_d, found_dates, reason = parse_with_ollama(text, today)
    if m_name and found_dates:
        return m_name, first_d, found_dates, reason, f"Ollama ({OLLAMA_MODEL})"

    # Tầng 3: Rule-based NLP Engine (Fallback an toàn)
    m_name, first_d, found_dates, reason = parse_with_rule_engine(text, today)
    engine = "Trợ lý AI Tiếng Việt"

    return m_name, first_d, found_dates, reason, engine

@app.route('/api/ai-parse-leave', methods=['POST'])
def api_ai_parse_leave():
    data = request.get_json(silent=True) or request.form
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'success': False, 'error': 'Vui lòng nhập tin nhắn xin nghỉ'})

    m_name, d_obj, reason, engine = ai_parse_message(message)
    if not m_name:
        return jsonify({'success': False, 'error': 'Chưa nhận diện được tên nhân viên trong tin nhắn (Phải thuộc 10 nhân sự của cửa hàng)'})
    if not d_obj:
        return jsonify({'success': False, 'error': 'Chưa nhận diện được ngày xin nghỉ (Ví dụ: 25/10/2026, ngày mai, thứ hai tuần sau)'})

    today = get_vn_today()
    if d_obj < today:
        return jsonify({'success': False, 'error': f'Ngày xin nghỉ ({d_obj.strftime("%d/%m/%Y")}) đã ở trong quá khứ'})

    weekday_vn = {
        'Monday': 'Thứ Hai', 'Tuesday': 'Thứ Ba', 'Wednesday': 'Thứ Tư',
        'Thursday': 'Thứ Năm', 'Friday': 'Thứ Sáu', 'Saturday': 'Thứ Bảy', 'Sunday': 'Chủ Nhật'
    }
    weekday_str = weekday_vn.get(d_obj.strftime('%A'), d_obj.strftime('%A'))

    return jsonify({
        'success': True,
        'member_name': m_name,
        'leave_date': d_obj.strftime('%Y-%m-%d'),
        'display_date': d_obj.strftime('%d/%m/%Y'),
        'weekday_vn': weekday_str,
        'reason': reason,
        'engine': engine
    })

def make_ai_chips(items, is_fill=False):
    """Tạo các nút bấm/chip nhanh trong khung chat AI để người dùng bấm 1 chạm"""
    fn_name = 'fillAiInput' if is_fill else 'askAiDuty'
    chips = []
    for label, query in items:
        esc_query = query.replace("'", "\\'").replace('"', '&quot;')
        bg = "#f0fdf4" if is_fill else "#eff6ff"
        border = "#bbf7d0" if is_fill else "#bfdbfe"
        color = "#15803d" if is_fill else "#1d4ed8"
        chips.append(
            f'<button type="button" onclick="{fn_name}(\'{esc_query}\')" '
            f'style="display:inline-flex; align-items:center; margin:3px 2px; padding:4px 10px; '
            f'background:{bg}; border:1px solid {border}; color:{color}; border-radius:12px; '
            f'font-size:0.78rem; font-weight:600; cursor:pointer; text-decoration:none; box-shadow:0 1px 2px rgba(0,0,0,0.04);">'
            f'{label}</button>'
        )
    return '<div style="margin-top:8px; display:flex; flex-wrap:wrap; gap:3px;">' + "".join(chips) + '</div>'

def get_admin_leave_statistics(all_time=False, specific_member=None):
    """
    Thống kê chi tiết ngày nghỉ cho Admin:
    - all_time=False: Trong chu kỳ hiện tại
    - all_time=True: Toàn bộ lịch sử (leaves + leaves_history)
    - specific_member: Lọc riêng 1 nhân viên nếu cần
    """
    today = get_vn_today()
    curr_cycle_key, curr_cycle_label, curr_start_d, curr_end_d = get_current_view_cycle(today)
    start_str = curr_start_d.strftime('%Y-%m-%d')
    end_str = curr_end_d.strftime('%Y-%m-%d')

    with get_db() as conn:
        if all_time:
            active_rows = conn.execute('SELECT leave_date, member_name, reason FROM leaves ORDER BY leave_date ASC').fetchall()
            hist_rows = conn.execute('SELECT leave_date, member_name, reason FROM leaves_history ORDER BY leave_date ASC').fetchall()
            period_label = "Toàn bộ lịch sử từ trước đến nay"
        else:
            active_rows = conn.execute('SELECT leave_date, member_name, reason FROM leaves WHERE leave_date >= ? AND leave_date <= ? ORDER BY leave_date ASC', (start_str, end_str)).fetchall()
            hist_rows = conn.execute('SELECT leave_date, member_name, reason FROM leaves_history WHERE leave_date >= ? AND leave_date <= ? ORDER BY leave_date ASC', (start_str, end_str)).fetchall()
            period_label = f"{curr_cycle_label} (từ {curr_start_d.strftime('%d/%m')} đến {curr_end_d.strftime('%d/%m/%Y')})"

    combined = []
    seen = set()
    for r in list(active_rows) + list(hist_rows):
        key = (r['leave_date'], r['member_name'])
        if key not in seen:
            seen.add(key)
            combined.append(dict(r))

    if specific_member:
        member_leaves = [item for item in combined if item['member_name'] == specific_member]
        return {
            'specific_member': specific_member,
            'period_label': period_label,
            'count': len(member_leaves),
            'leaves': member_leaves,
            'is_all_time': all_time
        }

    # Thống kê toàn bộ
    stats = {m: [] for m in ALL_STAFF}
    for item in combined:
        m = item['member_name']
        if m in stats:
            stats[m].append(item['leave_date'])

    sorted_stats = sorted(stats.items(), key=lambda x: len(x[1]), reverse=True)
    max_count = len(sorted_stats[0][1]) if sorted_stats else 0
    top_members = [m for m, d in sorted_stats if len(d) == max_count and max_count > 0]
    zero_members = [m for m, d in sorted_stats if len(d) == 0]
    total_leaves = sum(len(d) for m, d in sorted_stats)

    return {
        'period_label': period_label,
        'sorted_stats': sorted_stats,
        'max_count': max_count,
        'top_members': top_members,
        'zero_members': zero_members,
        'total_leaves': total_leaves,
        'is_all_time': all_time
    }

def format_leave_statistics_response(stats_data):
    if stats_data.get('specific_member'):
        m = stats_data['specific_member']
        cnt = stats_data['count']
        p_label = stats_data['period_label']
        leaves = stats_data['leaves']
        duty_badge = "🧹 Trực nhật" if m in DUTY_MEMBERS else "🔧 Kỹ thuật viên"
        
        lines = [
            f"📊 <strong>THỐNG KÊ NGÀY NGHỈ CỦA {m.upper()}</strong>",
            f"• Vai trò: <strong>{duty_badge}</strong>",
            f"• Thời gian: <em>{p_label}</em>",
            f"• Tổng số ngày nghỉ: <strong style='font-size:1.05rem; color:#f59e0b;'>{cnt} ngày</strong><br>"
        ]
        if cnt == 0:
            lines.append("🌟 <em>Nhân viên này chưa nghỉ ngày nào trong chu kỳ được chọn!</em>")
        else:
            lines.append("📋 <strong>Chi tiết các ca nghỉ:</strong>")
            for item in leaves:
                try:
                    d_dt = datetime.strptime(item['leave_date'], '%Y-%m-%d')
                    d_disp = d_dt.strftime('%d/%m/%Y')
                except Exception:
                    d_disp = item['leave_date']
                lines.append(f"• 📅 <strong>{d_disp}</strong>: Lý do \"<em>{item['reason']}</em>\"")
        
        chips = make_ai_chips([
            ("📊 Thống kê tất cả anh em", "Thống kê ai nghỉ nhiều nhất"),
            ("👑 Cho nghỉ cận ngày", f"Cho {m} nghỉ hôm nay"),
            ("🔔 Hôm nay ai trực?", "Hôm nay ai trực?"),
        ])
        return "<br>".join(lines) + chips

    p_label = stats_data['period_label']
    total = stats_data['total_leaves']
    top_members = stats_data['top_members']
    max_count = stats_data['max_count']
    zero_members = stats_data['zero_members']
    sorted_stats = stats_data['sorted_stats']
    
    lines = []
    lines.append("📊 <strong>BẢNG THỐNG KÊ NGÀY NGHỈ NHÂN SỰ TRẦN BÌNH AUTO</strong>")
    lines.append(f"📅 <em>{p_label} (Tổng cộng: <strong>{total}</strong> lượt nghỉ)</em><br>")
    
    if max_count > 0 and top_members:
        top_str = ", ".join([f"<strong>{m}</strong>" for m in top_members])
        lines.append(f"🏆 <strong>Top nghỉ nhiều nhất:</strong> {top_str} ({max_count} ngày)")
    
    if zero_members:
        zero_str = ", ".join([f"<strong>{m}</strong>" for m in zero_members])
        lines.append(f"🌟 <strong>Chưa nghỉ ngày nào ({len(zero_members)} người):</strong> {zero_str}")
    
    lines.append("<br>📋 <strong>Chi tiết từng thành viên:</strong>")
    for idx, (member, dates) in enumerate(sorted_stats, 1):
        duty_badge = "🧹" if member in DUTY_MEMBERS else "🔧"
        count = len(dates)
        if count == 0:
            lines.append(f"• {idx}. {duty_badge} <strong>{member}</strong>: 0 ngày <span style='color:#10b981;'>✓ Đi làm đủ</span>")
        else:
            dates_disp = ", ".join([datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m') for d in sorted(dates)[:5]])
            if len(dates) > 5:
                dates_disp += f" (+{len(dates)-5} ngày)"
            lines.append(f"• {idx}. {duty_badge} <strong>{member}</strong>: <strong>{count}</strong> ngày <span style='color:#94a3b8; font-size:0.8rem;'>({dates_disp})</span>")

    chips = make_ai_chips([
        ("📊 Thống kê toàn bộ lịch sử", "Thống kê toàn bộ lịch sử"),
        ("📊 Thống kê kỳ này", "Thống kê ngày nghỉ kỳ này"),
        ("👑 Duyệt nghỉ cận ngày", "Tôi muốn cho nhân viên nghỉ"),
        ("🎨 Đổi giao diện lễ hội", "Đổi giao diện ứng dụng"),
    ])
    return "<br>".join(lines) + chips

def get_admin_capabilities_response():
    chips = make_ai_chips([
        ("👑 Cho Vinh nghỉ hôm nay", "Cho Vinh nghỉ hôm nay"),
        ("📊 Ai nghỉ nhiều nhất kỳ này?", "Ai nghỉ nhiều nhất kỳ này?"),
        ("🌟 Ai chưa nghỉ ngày nào?", "Ai chưa nghỉ ngày nào?"),
        ("🎨 Đổi giao diện Tết", "Đổi giao diện Tết"),
        ("🎨 Đổi giao diện Halloween", "Đổi giao diện Halloween"),
    ])
    return (
        "👑 <strong>QUYỀN HẠN & ĐẶC QUYỀN CỦA QUẢN TRỊ VIÊN ADMIN TẠI TRẦN BÌNH AUTO:</strong><br><br>"
        "<strong>1. 🚀 Duyệt Nghỉ Cận Ngày & Bất Kỳ Ngày Nào:</strong><br>"
        "• Cho phép bất kỳ ai nghỉ <strong>Hôm nay, Ngày mai</strong> hoặc liên tiếp nhiều ngày không giới hạn (nhân viên thường chỉ được xin từ Ngày mốt trở đi).<br>"
        "• Nhắn trực tiếp với AI: <em>\"Cho Vinh nghỉ hôm nay\"</em>, <em>\"Admin duyệt cho Thái nghỉ mai và mốt\"</em>.<br><br>"
        "<strong>2. 📊 Báo Cáo & Thống Kê Ngày Nghỉ Toàn Diện:</strong><br>"
        "• Tra cứu tổng hợp ai nghỉ nhiều nhất, ai chưa nghỉ trong chu kỳ hoặc từ trước đến nay.<br>"
        "• Nhắn với AI: <em>\"Ai nghỉ nhiều nhất kỳ này?\"</em> hoặc <em>\"Thống kê lịch sử nghỉ\"</em>.<br><br>"
        "<strong>3. 🎨 Đổi Thử & Xem Giao Diện Ứng Dụng (Seasonal Themes):</strong><br>"
        "• Xem trước và kích hoạt các bộ giao diện: Tết Nguyên Đán, Halloween, Noel Giáng Sinh, Chào Năm Mới...<br>"
        "• Nhắn với AI: <em>\"Đổi giao diện Tết\"</em> hoặc <em>\"Đổi giao diện\"</em>.<br><br>"
        "<strong>4. ✏️ Chỉnh Sửa & Xóa Lịch Sử Nghỉ:</strong><br>"
        "• Toàn quyền sửa ngày, đổi người, hoặc xóa vĩnh viễn các ca nghỉ hiện tại và trong lịch sử.<br><br>"
        "<strong>5. 📜 Xem Nhật Ký Vết (Audit Trail):</strong><br>"
        "• Giám sát 50 thao tác gần nhất (ai thêm đơn, ai hủy đơn, ai đăng nhập admin...).<br>"
        f"{chips}"
    )

def get_admin_theme_response(theme_choice=None):
    theme_catalog_info = [
        ('tet', '🌸 Tết Cổ Truyền', 'Tết Nguyên Đán Cổ Truyền'),
        ('halloween', '🎃 Halloween', 'Đêm Hội Halloween'),
        ('christmas', '🎄 Noel Giáng Sinh', 'Giáng Sinh Ấm Áp & Noel'),
        ('new_year', '🥂 Chào Năm Mới', 'Chào Năm Mới & Countdown'),
        ('mid_autumn', '🏮 Trung Thu', 'Tết Trung Thu Đoàn Viên'),
        ('reset', '🔄 Tự Động / Mặc Định', 'Tự động theo thời gian thực')
    ]
    
    if theme_choice:
        if theme_choice == 'reset':
            session.pop('active_theme', None)
            return (
                "🎨 <strong>ĐÃ CHUYỂN VỀ GIAO DIỆN TỰ ĐỘNG!</strong><br>"
                "Hệ thống sẽ tự động cập nhật giao diện theo thời gian thực (ngày lễ, Tết).<br><br>"
                "<button type=\"button\" onclick=\"window.location.href='/?theme=reset'\" style=\"padding:7px 14px; background:linear-gradient(135deg, #2563eb, #1d4ed8); color:#fff; border:none; border-radius:14px; font-weight:700; cursor:pointer;\">🔄 Áp Dụng Ngay (Tải lại trang)</button>"
            )
        elif theme_choice in THEMES_CATALOG:
            session['active_theme'] = theme_choice
            theme_name = THEMES_CATALOG[theme_choice]['name']
            chips = make_ai_chips([(lbl, f"Đổi sang giao diện {lbl}") for k, lbl, _ in theme_catalog_info if k != theme_choice])
            return (
                f"🎨 <strong>ĐÃ KÍCH HOẠT GIAO DIỆN: {theme_name}!</strong><br>"
                f"Hệ thống đã chuyển sang phong cách lễ hội mới.<br><br>"
                f"<button type=\"button\" onclick=\"window.location.href='/?theme={theme_choice}'\" style=\"padding:8px 16px; background:linear-gradient(135deg, #16a34a, #15803d); color:#fff; border:none; border-radius:14px; font-weight:700; cursor:pointer; box-shadow:0 2px 8px rgba(22,163,74,0.4);\">✨ Bấm vào đây để tải lại trang với giao diện {theme_name}</button><br><br>"
                f"Hoặc chọn đổi thử giao diện khác bên dưới:{chips}"
            )

    chips = make_ai_chips([(lbl, f"Đổi sang giao diện {lbl}") for k, lbl, _ in theme_catalog_info])
    return (
        "🎨 <strong>BỘ SƯU TẬP GIAO DIỆN THEO MÙA (TRẦN BÌNH AUTO):</strong><br>"
        "Với quyền <strong>Quản Trị Admin</strong>, Sếp có thể bấm chọn ngay giao diện bên dưới để đổi thử trên toàn trang:<br>"
        f"{chips}"
    )

def answer_schedule_query(query):
    query_clean = query.strip()
    if not query_clean:
        return "Bạn muốn hỏi thông tin gì về lịch trực? (Ví dụ: 'Hôm nay ai trực?', 'Vinh trực ngày nào?', 'Thứ 2 tuần sau ai trực?')", "Trợ lý AI Tiếng Việt"
        
    cleanup_and_advance_checkpoint()
    schedule = get_schedule(days_ahead=30)
    weekday_vn_map = {
        'Monday': 'Thứ Hai', 'Tuesday': 'Thứ Ba', 'Wednesday': 'Thứ Tư',
        'Thursday': 'Thứ Năm', 'Friday': 'Thứ Sáu', 'Saturday': 'Thứ Bảy', 'Sunday': 'Chủ Nhật'
    }
    for item in schedule:
        item['weekday_vn'] = weekday_vn_map.get(item['weekday'], item['weekday'])
        
    today = get_vn_today()
    q_norm = remove_accents(query_clean.lower())

    # 1. Thử gọi Ollama nếu server đang hoạt động
    leaves_summary = get_leaves_summary(schedule)
    today_str = today.strftime('%Y-%m-%d')
    
    with get_db() as conn:
        shop_holidays_rows = conn.execute('SELECT holiday_date, reason FROM shop_holidays WHERE holiday_date >= ? ORDER BY holiday_date ASC LIMIT 10', (today_str,)).fetchall()

    # TỔNG HỢP DỮ LIỆU ĐỂ CUNG CẤP CHO LLM (GEMINI / OLLAMA)
    summary_lines = []
    for s in schedule[:14]:
        if s.get('is_holiday'):
            summary_lines.append(f"- {s['display_date']} ({s['weekday_vn']}): Tiệm đóng cửa ({s.get('holiday_reason')})")
        elif s.get('assigned'):
            summary_lines.append(f"- {s['display_date']} ({s['weekday_vn']}): {s['assigned']} trực vệ sinh 7h30")
    ctx = "\n".join(summary_lines)

    leaves_lines = [f"- {l['member_name']} nghỉ ngày {l['display_date']} ({l['weekday_vn']}), lý do: {l['reason']}" for l in leaves_summary[:10]]
    leaves_ctx = "\n".join(leaves_lines) if leaves_lines else "Hiện không có ai xin nghỉ."

    holidays_lines = [f"- Ngày {h['holiday_date']}: Tiệm đóng cửa ({h['reason']})" for h in shop_holidays_rows]
    holidays_ctx = "\n".join(holidays_lines) if holidays_lines else "Không có ngày nghỉ tiệm nào sắp tới."

    llm_prompt = f"""
Bạn là trợ lý AI quản lý lịch trực nhật vệ sinh 7h30 sáng và theo dõi ngày nghỉ tại "Trần Bình Auto".
Hôm nay là: {today.strftime('%d/%m/%Y')} ({weekday_vn_map.get(today.strftime('%A'))}).
Danh sách 8 người trực nhật vệ sinh: {', '.join(DUTY_MEMBERS)}.
Nhân sự không trực nhật: {', '.join(NON_DUTY_STAFF)}.
Toàn bộ 10 nhân sự: {', '.join(ALL_STAFF)}.

Lịch phân công trực nhật 14 ngày tới:
{ctx}

Danh sách các ca xin nghỉ hiện tại:
{leaves_ctx}

Lịch đóng cửa nghỉ lễ của tiệm:
{holidays_ctx}

Câu hỏi của người dùng: "{query_clean}"

Yêu cầu trả lời:
- Trả lời ngắn gọn, thân thiện, chính xác theo dữ liệu ở trên.
- Sử dụng Tiếng Việt tự nhiên, kèm emoji thích hợp.
- Format HTML đơn giản: in đậm tên người và ngày tháng bằng thẻ <strong>...</strong>, xuống dòng bằng <br>. Tuyệt đối không dùng dấu backtick ```.
"""

    # 1. Thử gọi Google Gemini Cloud AI trước nếu có API Key
    if get_gemini_api_key():
        try:
            gemini_ans = call_gemini_api(llm_prompt, timeout=4.5)
            if gemini_ans:
                clean_ans = gemini_ans.replace('```html', '').replace('```', '').strip().replace('\n', '<br>')
                return clean_ans, f"Google Gemini ({get_gemini_model()})"
        except Exception:
            pass

    # 2. Thử gọi Ollama Local nếu server đang hoạt động
    if is_ollama_online():
        try:
            req_data = json.dumps({
                "model": OLLAMA_MODEL,
                "prompt": llm_prompt,
                "stream": False
            }).encode('utf-8')
            req = urllib.request.Request(
                f"{OLLAMA_HOST}/api/generate",
                data=req_data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                ans = data.get('response', '').strip()
                if ans:
                    return ans.replace('\n', '<br>'), f"Ollama ({OLLAMA_MODEL})"
        except Exception:
            pass

    # 2. Xử lý bằng Bộ não NLP Tiếng Việt tích hợp (0ms, siêu tốc, chạy tốt trên PythonAnywhere)
    engine = "Trợ lý AI Tiếng Việt"

    # Kiểm tra xem có nhắc tới tên nhân viên nào không
    found_member = None
    for staff in sorted(ALL_STAFF, key=lambda s: len(s), reverse=True):
        staff_norm = remove_accents(staff.lower())
        if re.search(r'\b' + re.escape(staff_norm) + r'\b', q_norm):
            found_member = staff
            break

    # 1. Chào hỏi & Xã giao (Greetings & Chit-chat)
    if re.search(r'^(chao|xin chao|hello|hi|alo|ad|admin|bot|oi|hey)\b', q_norm):
        chips = make_ai_chips([
            ("🔔 Hôm nay ai trực?", "Hôm nay ai trực?"),
            ("🌱 Ngày mai ai trực?", "Ngày mai ai trực?"),
            ("🌴 Mai có ai nghỉ không?", "Mai có ai nghỉ không?"),
            ("📋 Lịch trực 7 ngày", "Lịch trực tuần này"),
            ("📝 Báo xin nghỉ", "Tôi muốn xin nghỉ"),
        ])
        return (
            "👋 <strong>Xin chào bạn!</strong> Mình là Trợ lý AI quản lý lịch trực nhật 7h30 sáng và theo dõi nghỉ của tiệm.<br>"
            f"Bạn cần mình hỗ trợ gì nè? 👇{chips}"
        ), engine

    # 2. Cảm ơn & Tạm biệt
    if re.search(r'\b(cam on|cảm ơn|thank|thanks|ok em|ok b|ok ad|tuyet voi)\b', q_norm):
        return "😊 Dạ không có chi ạ! Chúc bạn một ngày làm việc thật vui vẻ và nhiều may mắn nhé! Cần gì bạn cứ nhắn mình nha.", engine

    # 3. Quy định giờ giấc trực nhật
    if re.search(r'\b(may gio|quy dinh|luat|gio truc|ve sinh luc may gio|truc may gio)\b', q_norm):
        chips = make_ai_chips([
            ("🔔 Hôm nay ai trực?", "Hôm nay ai trực?"),
            ("🌱 Ngày mai ai trực?", "Ngày mai ai trực?"),
            ("📋 Lịch trực tuần này", "Lịch trực tuần này"),
        ])
        return (
            "⏰ <strong>Quy định trực nhật vệ sinh tại tiệm:</strong><br>"
            "• <strong>Giờ bắt đầu:</strong> Đúng <strong>7h30 sáng</strong> mỗi ngày.<br>"
            "• <strong>Đội trực chính (8 người luân phiên):</strong> Vinh, Dĩ, Ân, Bảo, Nguyên, Lợi, Thái, Duy.<br>"
            "• <strong>2 nhân sự không trực nhật:</strong> Bảo Mập, Phát.<br>"
            "• <strong>Cơ chế tự động:</strong> Nếu đến lượt ai mà người đó xin nghỉ hoặc tiệm đóng cửa, hệ thống sẽ <strong>tự động đôn người kế tiếp</strong> lên trực thay.<br>"
            f"👇 Bạn có thể tra cứu nhanh:{chips}"
        ), engine

    # 4. Hỏi xem hôm nay ai đi làm / ai có mặt
    if re.search(r'\b(co mat|di lam|ai di lam|ai lam hom nay|co ai lam)\b', q_norm):
        today_leaves = [l for l in leaves_summary if l['leave_date'] == today_str]
        if not today_leaves:
            chips = make_ai_chips([("🔔 Ai trực 7h30 sáng?", "Hôm nay ai trực?")])
            return f"🏢 Hôm nay ({today.strftime('%d/%m/%Y')}): Cả <strong>10 anh em</strong> đều đi làm đầy đủ, không có ai xin nghỉ!{chips}", engine
        else:
            leave_names = ", ".join([f"<strong>{l['member_name']}</strong>" for l in today_leaves])
            work_count = 10 - len(today_leaves)
            return f"🏢 Hôm nay ({today.strftime('%d/%m/%Y')}): Có {leave_names} xin nghỉ ({len(today_leaves)} người). Còn lại <strong>{work_count} anh em</strong> đi làm bình thường.", engine

    # 5. Hỏi về lịch trực của bản thân (Người dùng xưng tôi, em, mình... mà không nêu tên)
    is_asking_self = bool(re.search(r'\b(toi|em|minh|anh|chau|tui)\b', q_norm)) and bool(re.search(r'\b(truc|lich truc|ve sinh|khi nao|luot)\b', q_norm))
    if not found_member and is_asking_self:
        chips = make_ai_chips([(f"👤 {m}", f"{m} trực ngày nào?") for m in DUTY_MEMBERS])
        return (
            "❓ Bạn tên gì để mình xem lịch trực chính xác cho bạn nè?<br>"
            f"👉 Bạn bấm chọn tên mình bên dưới nhé:{chips}"
        ), engine

    # 6. Hỏi tổng hợp tuần này / tuần sau ("tuần này ai trực", "lịch trực tuần này", "lịch trực 7 ngày")
    if re.search(r'\b(tuan nay|tuan sau|tuan toi|7 ngay|ca tuan|lich truc tuan)\b', q_norm):
        if 'tuan sau' in q_norm or 'toi' in q_norm:
            start_idx = 7
            title = "Lịch trực 7 ngày tuần sau"
        else:
            start_idx = 0
            title = "Lịch trực 7 ngày sắp tới"
        
        lines = []
        for s in schedule[start_idx:start_idx+7]:
            if s.get('is_holiday'):
                lines.append(f"• 📅 <strong>{s['display_date']}</strong> ({s['weekday_vn']}): 🏢 Tiệm đóng cửa ({s.get('holiday_reason')})")
            else:
                lines.append(f"• 📅 <strong>{s['display_date']}</strong> ({s['weekday_vn']}): 👤 <strong>{s['assigned']}</strong> (7h30 sáng)")
        return f"📋 <strong>{title}:</strong><br>" + "<br>".join(lines), engine

    # ═══════════════════════════════════════════════════════════════════
    # NHÓM 1: CÂU HỎI VỀ NGÀY NGHỈ / AI NGHỈ (LEAVE INQUIRY)
    # ═══════════════════════════════════════════════════════════════════
    is_asking_leave = bool(re.search(r'\b(nghi|xin nghi|nghi phep|ai nghi|co ai nghi|co nghi khong|nghi khong|ai xin nghi|ngay nghi|lich nghi)\b', q_norm))
    if is_asking_leave:
        # A. Hỏi về ngày tiệm đóng cửa / nghỉ lễ
        if re.search(r'\b(tiem|cua hang|dong cua|le|tet)\b', q_norm):
            if not shop_holidays_rows:
                return "🏢 Hiện tại tiệm <strong>không có lịch đóng cửa / nghỉ lễ nào</strong> sắp tới (mở cửa hoạt động đầy đủ tất cả các ngày).", engine
            lines = [f"• 📅 <strong>{h['holiday_date']}</strong> — {h['reason']}" for h in shop_holidays_rows]
            return f"🏢 Các ngày tiệm đã cài đặt đóng cửa / nghỉ lễ sắp tới:<br>" + "<br>".join(lines), engine

        # B. Hỏi về 1 nhân viên cụ thể có xin nghỉ không (VD: Vinh có xin nghỉ không?, Dĩ nghỉ ngày nào?)
        if found_member:
            m_leaves = [l for l in leaves_summary if l['member_name'] == found_member]
            if m_leaves:
                lines = [f"• 📅 <strong>{l['display_date']}</strong> ({l['weekday_vn']}) — Lý do: <em>{l['reason']}</em>" for l in m_leaves]
                return f"📝 <strong>{found_member}</strong> có đăng ký xin nghỉ vào:<br>" + "<br>".join(lines), engine
            else:
                chips = make_ai_chips([
                    (f"📅 Xem lịch trực {found_member}", f"{found_member} trực ngày nào?"),
                    (f"📝 Báo nghỉ cho {found_member}", f"{found_member} xin nghỉ"),
                ])
                return f"✅ <strong>{found_member}</strong> hiện tại <strong>không có đơn xin nghỉ nào</strong> sắp tới (vẫn đi làm bình thường).{chips}", engine

        # C. Hỏi theo mốc thời gian cụ thể (hôm nay, ngày mai, ngày mốt, ngày DD/MM hoặc DD tháng MM, thứ X)
        target_date = None
        target_label = ''
        if re.search(r'\b(hom nay|nay|hom ni)\b', q_norm):
            target_date = today
            target_label = 'Hôm nay'
        elif re.search(r'\b(ngay mai|mai)\b', q_norm):
            target_date = today + timedelta(days=1)
            target_label = 'Ngày mai'
        elif re.search(r'\b(ngay mot|mot|ngay kia)\b', q_norm):
            target_date = today + timedelta(days=2)
            target_label = 'Ngày mốt'
        else:
            # Tìm ngày DD/MM hoặc DD tháng MM
            m_date = re.search(r'(\d{1,2})\s*(?:[/\-]|thang\s*|t\s*)(\d{1,2})', q_norm)
            if m_date:
                day_val, month_val = int(m_date.group(1)), int(m_date.group(2))
                try:
                    target_date = date(today.year, month_val, day_val)
                    if target_date < today and month_val < today.month:
                        target_date = date(today.year + 1, month_val, day_val)
                    target_label = f"Ngày {day_val:02d}/{month_val:02d}"
                except ValueError:
                    pass
            else:
                # Tìm thứ trong tuần
                weekdays_search = {
                    'thu 2': 'Thứ Hai', 'thu hai': 'Thứ Hai', 'thu 3': 'Thứ Ba', 'thu ba': 'Thứ Ba',
                    'thu 4': 'Thứ Tư', 'thu tu': 'Thứ Tư', 'thu 5': 'Thứ Năm', 'thu nam': 'Thứ Năm',
                    'thu 6': 'Thứ Sáu', 'thu sau': 'Thứ Sáu', 'thu 7': 'Thứ Bảy', 'thu bay': 'Thứ Bảy',
                    'chu nhat': 'Chủ Nhật', 'cn': 'Chủ Nhật'
                }
                for w_key, w_val in weekdays_search.items():
                    if re.search(r'\b' + re.escape(w_key) + r'\b', q_norm):
                        matches = [s for s in schedule if s['weekday_vn'] == w_val]
                        if matches:
                            target_s = matches[1] if ('tuan sau' in q_norm or 'toi' in q_norm) and len(matches) > 1 else matches[0]
                            try:
                                target_date = datetime.strptime(target_s['date_str'], '%Y-%m-%d').date()
                                target_label = f"{target_s['weekday_vn']}"
                            except Exception:
                                pass
                        break

        if target_date:
            d_str = target_date.strftime('%Y-%m-%d')
            disp_d = target_date.strftime('%d/%m/%Y')
            w_vn = weekday_vn_map.get(target_date.strftime('%A'), '')
            
            # Kiểm tra xem ngày đó tiệm có đóng cửa không
            holiday_match = next((h for h in shop_holidays_rows if h['holiday_date'] == d_str), None)
            if holiday_match:
                return f"🏢 Vào <strong>{target_label}</strong> ({disp_d}, {w_vn}): <strong>Tiệm đóng cửa nghỉ lễ</strong> ({holiday_match['reason']}). Toàn bộ 10 anh em đều được nghỉ!", engine

            on_date_leaves = [l for l in leaves_summary if l['leave_date'] == d_str]
            if not on_date_leaves:
                return f"🌴 Vào <strong>{target_label}</strong> (ngày {disp_d}, {w_vn}): <strong>Không có ai xin nghỉ!</strong> Cả 10 anh em đều đi làm đầy đủ.", engine
            
            lines = [f"• 👤 <strong>{l['member_name']}</strong> — Lý do: <em>{l['reason']}</em>" for l in on_date_leaves]
            return f"📋 Vào <strong>{target_label}</strong> (ngày {disp_d}, {w_vn}) có <strong>{len(on_date_leaves)} người xin nghỉ</strong>:<br>" + "<br>".join(lines), engine

        # D. Hỏi tổng quát chung (VD: "Có ai xin nghỉ không?", "Dạo này ai nghỉ?", "Danh sách xin nghỉ")
        if not leaves_summary:
            return "🌴 Hiện tại cả 10 anh em đều đang có lịch đi làm đầy đủ, <strong>không có ai xin nghỉ</strong> sắp tới!", engine
        lines = [f"• 👤 <strong>{item['member_name']}</strong> nghỉ ngày <strong>{item['display_date']}</strong> ({item['weekday_vn']}) — Lý do: <em>{item['reason']}</em>" for item in leaves_summary[:6]]
        return f"📋 Danh sách các ca xin nghỉ sắp tới tại Trần Bình Auto ({len(leaves_summary)} ca):<br>" + "<br>".join(lines), engine

    # ═══════════════════════════════════════════════════════════════════
    # NHÓM 2: CÂU HỎI VỀ TRỰC NHẬT (DUTY INQUIRY)
    # ═══════════════════════════════════════════════════════════════════
    # 2.1. Hỏi về 1 nhân viên cụ thể trực ngày nào
    if found_member:
        if found_member in NON_DUTY_STAFF:
            return f"ℹ️ <strong>{found_member}</strong> thuộc nhóm nhân sự không trực nhật vệ sinh 7h30 sáng tại Trần Bình Auto.", engine

        my_duties = [s for s in schedule if s.get('assigned') == found_member]
        if not my_duties:
            return f"Hiện trong 30 ngày tới không thấy ca trực nào của <strong>{found_member}</strong> (có thể do trùng ngày tiệm đóng cửa hoặc có đơn xin nghỉ).", engine

        lines = [f"• 📅 <strong>{d['display_date']}</strong> ({d['weekday_vn']})" for d in my_duties[:4]]
        res = f"👉 Các ca trực sắp tới của <strong>{found_member}</strong> (7h30 sáng):<br>" + "<br>".join(lines)
        if len(my_duties) > 4:
            res += f"<br><small style='color:#64748b;'>Và còn {len(my_duties)-4} ca nữa trong các tuần tiếp theo.</small>"
        return res, engine

    # 2.2. Hỏi hôm nay ai trực
    if re.search(r'\b(hom nay|nay|hom ni)\b', q_norm):
        s0 = schedule[0] if schedule else None
        if s0:
            if s0.get('is_holiday'):
                return f"🏢 Hôm nay ({s0['display_date']}, {s0['weekday_vn']}): <strong>Tiệm đóng cửa nghỉ lễ</strong> ({s0.get('holiday_reason')}). Cả tiệm không phải trực!", engine
            chips = make_ai_chips([("🌱 Ngày mai ai trực?", "Ngày mai ai trực?"), ("🌴 Hôm nay ai nghỉ?", "Hôm nay có ai nghỉ không?")])
            return f"🔔 Hôm nay (<strong>{s0['display_date']}</strong>, {s0['weekday_vn']}): Người trực chính 7h30 sáng là <strong>{s0['assigned']}</strong>.{chips}", engine

    # 2.3. Hỏi ngày mai ai trực
    if re.search(r'\b(ngay mai|mai)\b', q_norm):
        s1 = schedule[1] if len(schedule) > 1 else None
        if s1:
            if s1.get('is_holiday'):
                return f"🏢 Ngày mai ({s1['display_date']}, {s1['weekday_vn']}): <strong>Tiệm đóng cửa</strong> ({s1.get('holiday_reason')}).", engine
            chips = make_ai_chips([("🌿 Ngày mốt ai trực?", "Ngày mốt ai trực?"), ("🌴 Mai có ai nghỉ không?", "Mai có ai nghỉ không?")])
            return f"🌱 Ngày mai (<strong>{s1['display_date']}</strong>, {s1['weekday_vn']}): Người trực là <strong>{s1['assigned']}</strong> (7h30 sáng).{chips}", engine

    # 2.4. Hỏi ngày mốt / ngày kia
    if re.search(r'\b(ngay mot|mot|ngay kia)\b', q_norm):
        s2 = schedule[2] if len(schedule) > 2 else None
        if s2:
            return f"🌿 Ngày mốt (<strong>{s2['display_date']}</strong>, {s2['weekday_vn']}): Người trực là <strong>{s2['assigned']}</strong> (7h30 sáng).", engine

    # 2.5. Hỏi theo ngày cụ thể (VD: 25/10 ai trực, ngày 20-10, 25 tháng 10 ai trực)
    m = re.search(r'(\d{1,2})\s*(?:[/\-]|thang\s*|t\s*)(\d{1,2})', q_norm)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        for s in schedule:
            d_parts = [int(p) for p in s['display_date'].split('/')]
            if d_parts[0] == day and d_parts[1] == month:
                if s.get('is_holiday'):
                    return f"🏢 Ngày <strong>{s['display_date']}</strong> ({s['weekday_vn']}): Tiệm đóng cửa ({s.get('holiday_reason')}).", engine
                return f"📅 Vào ngày <strong>{s['display_date']}</strong> ({s['weekday_vn']}): Người trực là <strong>{s['assigned']}</strong> (7h30 sáng).", engine
        return f"Không tìm thấy lịch của ngày {day}/{month} trong danh sách 30 ngày tới.", engine

    # 2.6. Hỏi theo thứ trong tuần (VD: thứ 2 tuần sau ai trực, chủ nhật ai trực)
    weekdays_search = {
        'thu 2': 'Thứ Hai', 'thu hai': 'Thứ Hai',
        'thu 3': 'Thứ Ba', 'thu ba': 'Thứ Ba',
        'thu 4': 'Thứ Tư', 'thu tu': 'Thứ Tư',
        'thu 5': 'Thứ Năm', 'thu nam': 'Thứ Năm',
        'thu 6': 'Thứ Sáu', 'thu sau': 'Thứ Sáu',
        'thu 7': 'Thứ Bảy', 'thu bay': 'Thứ Bảy',
        'chu nhat': 'Chủ Nhật', 'cn': 'Chủ Nhật'
    }
    for w_key, w_val in weekdays_search.items():
        if re.search(r'\b' + re.escape(w_key) + r'\b', q_norm):
            matches = [s for s in schedule if s['weekday_vn'] == w_val]
            if matches:
                target = matches[1] if ('tuan sau' in q_norm or 'toi' in q_norm) and len(matches) > 1 else matches[0]
                if target.get('is_holiday'):
                    return f"🏢 Vào <strong>{target['weekday_vn']}</strong> (ngày {target['display_date']}): Tiệm đóng cửa ({target.get('holiday_reason')}).", engine
                return f"📅 Vào <strong>{target['weekday_vn']}</strong> (ngày {target['display_date']}): Người trực là <strong>{target['assigned']}</strong> (7h30 sáng).", engine

    # ═══════════════════════════════════════════════════════════════════
    # NHÓM 3: KHÔNG HIỂU RÕ Ý -> HỎI LẠI NGƯỜI DÙNG KÈM NÚT BẤM GỢI Ý
    # ═══════════════════════════════════════════════════════════════════
    chips = make_ai_chips([
        ("🔔 Hôm nay ai trực?", "Hôm nay ai trực?"),
        ("🌱 Ngày mai ai trực?", "Ngày mai ai trực?"),
        ("🌴 Mai có ai nghỉ không?", "Mai có ai nghỉ không?"),
        ("📋 Lịch trực 7 ngày", "Lịch trực tuần này"),
        ("📝 Báo xin nghỉ", "Tôi muốn xin nghỉ"),
    ])
    return (
        f"🤔 Trợ lý chưa hiểu rõ ý của bạn: <em>\"{query_clean}\"</em>.<br>"
        f"👉 Bạn có thể nói rõ hơn hoặc bấm chọn nhanh câu hỏi bên dưới nhé:{chips}"
    ), engine

@app.route('/api/ai-chat-schedule', methods=['POST'])
def api_ai_chat_schedule():
    data = request.get_json(silent=True) or request.form
    question = data.get('question', '').strip()
    if not question:
        return jsonify({'success': False, 'error': 'Vui lòng nhập câu hỏi'})

    q_norm = remove_accents(question.lower())
    admin_mode = is_admin()

    # ═══════════════════════════════════════════════════════════════════
    # 0. ĐẶC QUYỀN ADMIN: XỬ LÝ CÁC CÂU HỎI QUẢN TRỊ VIÊN
    # ═══════════════════════════════════════════════════════════════════

    # 0.1. Hỏi về Quyền hạn / Hướng dẫn Admin
    if re.search(r'\b(admin\s+(?:lam|co\s+the|duoc|chuc\s+nang)|quyen\s+admin|chuc\s+nang\s+admin|huong\s+dan\s+admin|dac\s+quyen\s+admin|vai\s+tro\s+admin)\b', q_norm):
        return jsonify({
            'success': True,
            'is_leave_intent': False,
            'is_admin_mode': admin_mode,
            'answer': get_admin_capabilities_response(),
            'engine': 'Trợ lý Admin'
        })

    # 0.2. Thống kê ngày nghỉ / Lịch sử nghỉ của các thành viên
    is_stats_query = bool(re.search(r'\b(thong\s+ke|ai\s+ngh[i|y]\s+nhieu\s+nhat|ai\s+ngh[i|y]\s+it\s+nhat|ai\s+chua\s+ngh[i|y]|lich\s+su\s+ngh[i|y]|tong\s+hop\s+ngh[i|y]|so\s+ngay\s+ngh[i|y]|bao\s+cao\s+ngh[i|y]|ai\s+off\s+nhieu\s+nhat)\b', q_norm))
    if is_stats_query:
        target_staff = None
        for staff in sorted(ALL_STAFF, key=lambda s: len(s), reverse=True):
            if re.search(r'\b' + re.escape(remove_accents(staff.lower())) + r'\b', q_norm):
                target_staff = staff
                break
        is_all_time = bool(re.search(r'\b(toan\s+bo|tat\s+ca|tat\s+ca\s+cac\s+ky|lich\s+su|all)\b', q_norm))
        stats_data = get_admin_leave_statistics(all_time=is_all_time, specific_member=target_staff)
        ans = format_leave_statistics_response(stats_data)
        return jsonify({
            'success': True,
            'is_leave_intent': False,
            'is_admin_mode': admin_mode,
            'answer': ans,
            'engine': 'Thống kê Admin'
        })

    # 0.3. Đổi giao diện / Xem thử giao diện (Seasonal Themes)
    is_theme_query = bool(re.search(r'\b(doi\s+giao\s+dien|xem\s+giao\s+dien|giao\s+dien|theme|doi\s+theme|mau\s+giao\s+dien|xem\s+thu\s+giao\s+dien)\b', q_norm))
    if is_theme_query:
        if not admin_mode:
            chips = make_ai_chips([("🔔 Hôm nay ai trực?", "Hôm nay ai trực?"), ("🌱 Ngày mai ai trực?", "Ngày mai ai trực?")])
            return jsonify({
                'success': True,
                'is_leave_intent': False,
                'is_admin_mode': False,
                'answer': (
                    "🔒 <strong>QUYỀN QUẢN TRỊ ADMIN:</strong><br>"
                    "Tính năng đổi thử giao diện theo mùa chỉ dành riêng cho Quản trị viên (Admin).<br>"
                    f"👉 Bạn vui lòng cuộn xuống cuối trang và bấm nút <strong>Admin</strong> để đăng nhập quản trị nhé!{chips}"
                ),
                'engine': 'Trợ lý AI'
            })
        
        chosen_theme = None
        if re.search(r'\b(tet|nguyen\s+dan|xuan|am\s+lich)\b', q_norm):
            chosen_theme = 'tet'
        elif re.search(r'\b(halloween|ma\s+quai|bi\s+ngo)\b', q_norm):
            chosen_theme = 'halloween'
        elif re.search(r'\b(noel|giang\s+sinh|christmas)\b', q_norm):
            chosen_theme = 'christmas'
        elif re.search(r'\b(nam\s+moi|new\s+year|countdown|tet\s+tay)\b', q_norm):
            chosen_theme = 'new_year'
        elif re.search(r'\b(trung\s+thu|mid\s+autumn)\b', q_norm):
            chosen_theme = 'mid_autumn'
        elif re.search(r'\b(mac\s+dinh|tu\s+dong|reset|ban\s+dau|tro\s+ve)\b', q_norm):
            chosen_theme = 'reset'
        
        return jsonify({
            'success': True,
            'is_leave_intent': False,
            'is_admin_mode': True,
            'answer': get_admin_theme_response(chosen_theme),
            'engine': 'Quản lý Giao diện'
        })

    # 0.4. Nếu là câu chào hỏi và đang ở chế độ Admin:
    if admin_mode and re.search(r'^(chao|xin chao|hello|hi|alo|ad|admin|bot|oi|hey)\b', q_norm):
        chips = make_ai_chips([
            ("👑 Cho nghỉ cận ngày", "Tôi muốn cho nhân viên nghỉ"),
            ("📊 Ai nghỉ nhiều nhất kỳ này?", "Ai nghỉ nhiều nhất kỳ này?"),
            ("🌟 Ai chưa nghỉ?", "Ai chưa nghỉ ngày nào?"),
            ("🎨 Đổi giao diện lễ hội", "Đổi giao diện ứng dụng"),
            ("👑 Quyền Admin làm gì?", "Admin có thể làm được những gì?"),
            ("🔔 Hôm nay ai trực?", "Hôm nay ai trực?"),
        ])
        return jsonify({
            'success': True,
            'is_leave_intent': False,
            'is_admin_mode': True,
            'answer': (
                "👋 <strong>Xin chào Sếp (Admin Trần Bình Auto)!</strong> 👑<br>"
                "Bạn đang có <strong>Quyền Quản Trị Tối Cao</strong>. AI có thể giúp Sếp:<br>"
                "• 🚀 Duyệt nghỉ cận ngày (hôm nay, mai, mốt, nhiều ngày liên tiếp).<br>"
                "• 📊 Tra cứu thống kê ai nghỉ nhiều nhất, ai chưa nghỉ.<br>"
                "• 🎨 Đổi thử giao diện ứng dụng (Tết, Halloween, Noel...).<br>"
                f"Sếp cần kiểm tra hoặc điều phối gì ạ? 👇{chips}"
            ),
            'engine': 'Trợ lý Admin'
        })

    # ═══════════════════════════════════════════════════════════════════
    # 1. NHẬN DIỆN Ý ĐỊNH BÁO NGHỈ / DUYỆT NGHỈ (LEAVE INTENT)
    # ═══════════════════════════════════════════════════════════════════
    has_leave_intent_verbs = bool(re.search(r'\b(xin\s+ngh[i|y]|muon\s+ngh[i|y]|can\s+ngh[i|y]|dinh\s+ngh[i|y]|tinh\s+ngh[i|y]|bao\s+ngh[i|y]|dang\s+ky\s+ngh[i|y]|ngh[i|y]\s+phep|cho\s+(?:toi|em|anh|minh|chau|tui)?\s*ngh[i|y]|xin\s+off|muon\s+off|bao\s+off|duyet\s+ngh[i|y]|phe\s+duyet\s+ngh[i|y]|dac\s+cach\s+ngh[i|y]|cho\s+ngh[i|y]|cho\s+phep\s+.*ngh[i|y])\b', q_norm))
    first_person_leave = bool(re.search(r'\b(toi|em|minh|chau|tui)\s+(muon|xin|can|dinh|tinh|se)?\s*ngh[i|y]\b', q_norm))

    # Nhận diện câu hỏi tra cứu người nghỉ thông thường
    is_inquiry = bool(re.search(r'\b(co\s+ai\s+nghi|ai\s+nghi|ai\s+xin\s+nghi|co\s+nguoi\s+nghi|co\s+ai\s+off|ai\s+off|danh\s+sach\s+nghi|xem\s+nghi|khi\s+nao\s+nghi|ngay\s+nao\s+nghi|nghi\s+ngay\s+nao)\b', q_norm))
    is_asking_if_someone_leave = bool(re.search(r'\b(co\s+.*ngh[i|y]|ngh[i|y]\s+.*(?:khong|chua|\?))\b', q_norm)) and not (has_leave_intent_verbs or first_person_leave)
    is_pure_question = is_inquiry or is_asking_if_someone_leave

    has_staff_and_leave = bool(re.search(r'\bngh[i|y]\b', q_norm)) and any(remove_accents(s.lower()) in q_norm for s in ALL_STAFF)
    is_leave_statement = (has_leave_intent_verbs or first_person_leave or has_staff_and_leave) and not is_pure_question

    if is_leave_statement:
        m_name, first_d, found_dates, reason, engine = ai_parse_message(question)
        today = get_vn_today()
        # Quy định nhân viên: Cho phép từ Ngày mốt (Không nhận Hôm nay và Ngày mai)
        min_allowed_date = today + timedelta(days=2)
        min_allowed_str = min_allowed_date.strftime('%Y-%m-%d')
        min_allowed_disp = min_allowed_date.strftime('%d/%m/%Y')
        weekday_vn = {
            'Monday': 'Thứ Hai', 'Tuesday': 'Thứ Ba', 'Wednesday': 'Thứ Tư',
            'Thursday': 'Thứ Năm', 'Friday': 'Thứ Sáu', 'Saturday': 'Thứ Bảy', 'Sunday': 'Chủ Nhật'
        }
        min_allowed_w = weekday_vn.get(min_allowed_date.strftime('%A'), '')
        m_prefix = f"{m_name} " if m_name else ""

        if found_dates:
            past_dates = sorted([d for d in found_dates if d < today])
            is_allow_near = admin_mode or (m_name == 'Nguyên')
            if is_allow_near:
                # ĐẶC QUYỀN ADMIN hoặc NGOẠI LỆ CHO NGUYÊN: Cho phép duyệt bất kỳ ngày nào từ hôm nay trở đi (cận ngày, liên tiếp)
                near_dates = []
                valid_dates = sorted([d for d in found_dates if d >= today])
            else:
                near_dates = sorted([d for d in found_dates if today <= d < min_allowed_date])
                future_valid_dates = sorted([d for d in found_dates if d >= min_allowed_date])
                valid_dates = future_valid_dates

            # TRƯỜNG HỢP 1 (Chỉ với Nhân viên thường không phải Nguyên): Chọn ngày cận -> Từ chối & hướng dẫn liên hệ Admin
            if not is_allow_near and near_dates and not valid_dates:
                near_disp = ', '.join([d.strftime('%d/%m/%Y') for d in near_dates])
                chips = make_ai_chips([
                    (f"📅 Nghỉ từ {min_allowed_date.strftime('%d/%m')}", f"{m_prefix}xin nghỉ ngày {min_allowed_date.strftime('%d/%m')}"),
                    (f"📅 Nghỉ 2 ngày từ {min_allowed_date.strftime('%d/%m')}", f"{m_prefix}xin nghỉ 2 ngày từ {min_allowed_date.strftime('%d/%m')}"),
                    ("🔔 Hôm nay ai trực?", "Hôm nay ai trực?"),
                    ("🌱 Ngày mai ai trực?", "Ngày mai ai trực?"),
                ])
                return jsonify({
                    'success': True,
                    'is_leave_intent': False,
                    'is_admin_mode': False,
                    'answer': (
                        f"⛔ <strong>KHÔNG ĐƯỢC PHÉP XIN NGHỈ CẬN NGÀY!</strong><br>"
                        f"Theo quy định của Trần Bình Auto, bạn <strong>không được tự đăng ký xin nghỉ vào Hôm nay và Ngày mai</strong> "
                        f"(ngày bạn chọn: <strong>{near_disp}</strong>) để tránh thiếu hụt nhân sự và kịp sắp xếp trực nhật.<br>"
                        f"👉 Ngày đăng ký sớm nhất có thể nhận là từ <strong>{min_allowed_disp}</strong> ({min_allowed_w} - Ngày mốt).<br>"
                        f"📞 <em>Trường hợp có việc khẩn cấp hoặc đột xuất, bạn vui lòng <strong>liên hệ trực tiếp với Quản lý / Admin</strong> để được xử lý nhé!</em>{chips}"
                    ),
                    'engine': engine
                })

            if not valid_dates and past_dates:
                earliest_disp = today.strftime('%d/%m/%Y') if admin_mode else min_allowed_disp
                chips = make_ai_chips([
                    (f"📅 Nghỉ từ {earliest_disp}", f"{m_prefix}xin nghỉ ngày {earliest_disp}"),
                ])
                return jsonify({
                    'success': True,
                    'is_leave_intent': False,
                    'is_admin_mode': admin_mode,
                    'answer': f"⚠️ Các ngày bạn yêu cầu đều đã ở trong quá khứ nên hệ thống không nhận đơn được nữa.<br>👉 Ngày xin nghỉ sớm nhất có thể nhận là từ <strong>{earliest_disp}</strong>.{chips}",
                    'engine': engine
                })

            # TRƯỜNG HỢP 2: Có các ngày hợp lệ
            leave_dates_str = [d.strftime('%Y-%m-%d') for d in valid_dates]
            display_dates = [f"{d.strftime('%d/%m/%Y')} ({weekday_vn.get(d.strftime('%A'), '')})" for d in valid_dates]

            near_warning_note = ""
            if not is_allow_near and near_dates:
                near_disp = ', '.join([d.strftime('%d/%m') for d in near_dates])
                near_warning_note = f"• ⚠️ <strong>Các ngày cận ({near_disp})</strong>: Đã bị loại bỏ do quy định không nhận đơn Hôm nay và Ngày mai (vui lòng liên hệ Admin nếu cần nghỉ gấp)."

            if m_name:
                conflict_notes = []
                if admin_mode:
                    conflict_notes.append("• 👑 <strong>ĐẶC QUYỀN ADMIN:</strong> Cho phép duyệt nghỉ cận ngày & liên tiếp theo thẩm quyền quản lý.")
                if not is_allow_near and near_warning_note:
                    conflict_notes.append(near_warning_note)
                has_any_conflict = False

                with get_db() as conn:
                    for d, d_str, disp in zip(valid_dates, leave_dates_str, display_dates):
                        my_existing = conn.execute(
                            'SELECT reason FROM leaves WHERE leave_date = ? AND member_name = ?',
                            (d_str, m_name)
                        ).fetchone()
                        existing_leaves = conn.execute(
                            'SELECT member_name, reason FROM leaves WHERE leave_date = ? AND member_name != ?',
                            (d_str, m_name)
                        ).fetchall()
                        holiday_match = conn.execute(
                            'SELECT reason FROM shop_holidays WHERE holiday_date = ?',
                            (d_str,)
                        ).fetchone()

                        if holiday_match:
                            conflict_notes.append(f"• <strong>{d.strftime('%d/%m')}</strong>: 🏢 Tiệm đóng cửa ({holiday_match['reason']}).")
                        elif my_existing:
                            conflict_notes.append(f"• <strong>{d.strftime('%d/%m')}</strong>: ℹ️ Đã có đơn trước đó (Lý do cũ: <em>\"{my_existing['reason']}\"</em>) ➔ Sẽ cập nhật lý do mới.")
                        elif existing_leaves:
                            has_any_conflict = True
                            names = ", ".join([f"<strong>{p['member_name']}</strong>" for p in existing_leaves])
                            conflict_notes.append(f"• <strong>{d.strftime('%d/%m')}</strong>: ⚠️ Đã có {names} xin nghỉ trước.")

                if not conflict_notes:
                    summary_note = f"✅ Toàn bộ {len(valid_dates)} ngày này hiện chưa có ai xin nghỉ (Tránh được trùng lịch)."
                else:
                    summary_note = "<br>".join(conflict_notes)

                # Tạo text hiển thị tóm tắt
                if len(valid_dates) == 1:
                    display_date = valid_dates[0].strftime('%d/%m/%Y')
                    weekday_info = weekday_vn.get(valid_dates[0].strftime('%A'), '')
                else:
                    is_consecutive = all((valid_dates[i] - valid_dates[i-1]).days == 1 for i in range(1, len(valid_dates)))
                    if is_consecutive:
                        display_date = f"Từ {valid_dates[0].strftime('%d/%m/%Y')} đến {valid_dates[-1].strftime('%d/%m/%Y')}"
                        weekday_info = f"{len(valid_dates)} ngày liên tiếp"
                    else:
                        dates_str_list = [d.strftime('%d/%m/%Y') for d in valid_dates]
                        display_date = " & ".join(dates_str_list)
                        weekday_info = f"{len(valid_dates)} ngày"

                return jsonify({
                    'success': True,
                    'is_leave_intent': True,
                    'is_admin_mode': admin_mode,
                    'member_name': m_name,
                    'leave_date': leave_dates_str[0],
                    'leave_dates': leave_dates_str,
                    'display_date': display_date,
                    'weekday_vn': weekday_info,
                    'reason': reason,
                    'has_conflict': has_any_conflict,
                    'conflict_note': summary_note,
                    'engine': 'Trợ lý Admin' if admin_mode else engine
                })
            else:
                # Chưa biết tên nhân viên -> Hỏi lại kèm nút chọn tên
                if len(valid_dates) > 1:
                    dates_disp = ' và '.join([d.strftime('%d/%m') for d in valid_dates])
                    lbl = f"các ngày <strong>{dates_disp}</strong> ({len(valid_dates)} ngày)"
                else:
                    dates_disp = valid_dates[0].strftime('%d/%m')
                    lbl = f"ngày <strong>{dates_disp}</strong>"

                near_prefix = ""
                if not admin_mode and near_dates:
                    near_disp = ', '.join([d.strftime('%d/%m') for d in near_dates])
                    near_prefix = f"⚠️ <em>Lưu ý: Các ngày cận ({near_disp}) đã được loại bỏ do quy định không nhận đơn cận ngày.</em><br>"

                role_prompt = "Sếp muốn duyệt cho ai trong 10 anh em Trần Bình Auto nghỉ vậy ạ?" if admin_mode else "Bạn là ai trong 10 anh em Trần Bình Auto? Vui lòng bấm chọn tên của bạn bên dưới để tạo đơn ngay nhé:"
                prefix_cmd = "Cho " if admin_mode else ""
                chips = make_ai_chips([(f"👤 {m}", f"{prefix_cmd}{m} xin nghỉ ngày {dates_disp}") for m in ALL_STAFF])
                return jsonify({
                    'success': True,
                    'is_leave_intent': False,
                    'is_admin_mode': admin_mode,
                    'answer': (
                        f"{near_prefix}"
                        f"📝 Trợ lý đã ghi nhận muốn đăng ký nghỉ vào {lbl}.<br>"
                        f"❓ {role_prompt}{chips}"
                    ),
                    'engine': engine
                })
        else:
            # Không phát hiện được ngày nào
            if admin_mode:
                if m_name:
                    chips = make_ai_chips([
                        (f"👑 Cho {m_name} nghỉ hôm nay", f"Cho {m_name} nghỉ hôm nay"),
                        (f"👑 Cho {m_name} nghỉ ngày mai", f"Cho {m_name} nghỉ ngày mai"),
                        (f"👑 Cho {m_name} nghỉ mai & mốt", f"Cho {m_name} nghỉ ngày mai và ngày mốt"),
                        (f"👑 Cho {m_name} nghỉ 3 ngày", f"Cho {m_name} nghỉ 3 ngày từ ngày mai"),
                    ])
                    return jsonify({
                        'success': True,
                        'is_leave_intent': False,
                        'is_admin_mode': True,
                        'answer': (
                            f"👑 <strong>Sếp muốn duyệt cho {m_name} nghỉ vào ngày nào ạ?</strong><br>"
                            f"Admin có quyền duyệt nghỉ ngay hôm nay, ngày mai hoặc nhiều ngày liên tiếp:{chips}"
                        ),
                        'engine': 'Trợ lý Admin'
                    })
                else:
                    chips = make_ai_chips([
                        ("👑 Cho Vinh nghỉ hôm nay", "Cho Vinh nghỉ hôm nay"),
                        ("👑 Cho Bảo Mập nghỉ ngày mai", "Cho Bảo Mập nghỉ ngày mai"),
                        ("👑 Cho Thái nghỉ mai & mốt", "Cho Thái nghỉ ngày mai và ngày mốt"),
                        ("👑 Cho Ân nghỉ 3 ngày", "Cho Ân nghỉ 3 ngày từ ngày mai"),
                    ])
                    return jsonify({
                        'success': True,
                        'is_leave_intent': False,
                        'is_admin_mode': True,
                        'answer': (
                            "👑 <strong>Sếp muốn duyệt cho ai nghỉ và vào ngày nào ạ?</strong><br>"
                            "Với quyền Quản Trị Admin, Sếp có thể cho bất kỳ ai nghỉ hôm nay, ngày mai, ngày mốt hoặc nhiều ngày liên tiếp không cần cách ngày.<br>"
                            f"👉 Sếp có thể nhắn trực tiếp câu lệnh hoặc chọn gợi ý bên dưới:{chips}"
                        ),
                        'engine': 'Trợ lý Admin'
                    })
            else:
                if m_name:
                    if m_name == 'Nguyên':
                        chips = make_ai_chips([
                            (f"📅 Nghỉ hôm nay", f"{m_name} xin nghỉ hôm nay"),
                            (f"📅 Nghỉ ngày mai", f"{m_name} xin nghỉ ngày mai"),
                            (f"📅 Nghỉ ngày mốt", f"{m_name} xin nghỉ ngày mốt"),
                            ("🗓️ Nghỉ tuần sau", f"{m_name} xin nghỉ tuần sau"),
                        ])
                        return jsonify({
                            'success': True,
                            'is_leave_intent': False,
                            'is_admin_mode': False,
                            'answer': (
                                f"❓ Bạn muốn đăng ký cho <strong>{m_name}</strong> xin nghỉ vào ngày nào vậy bạn?<br>"
                                f"👉 Bạn có thể nhắn ngày hoặc bấm chọn nhanh bên dưới:{chips}"
                            ),
                            'engine': engine
                        })
                    chips = make_ai_chips([
                        (f"⚡ Nghỉ ngày mốt ({min_allowed_date.strftime('%d/%m')})", f"{m_name} xin nghỉ ngày mốt"),
                        (f"📅 Nghỉ 2 ngày từ {min_allowed_date.strftime('%d/%m')}", f"{m_name} xin nghỉ 2 ngày từ {min_allowed_date.strftime('%d/%m')}"),
                        (f"📅 Nghỉ 3 ngày từ {min_allowed_date.strftime('%d/%m')}", f"{m_name} xin nghỉ 3 ngày từ {min_allowed_date.strftime('%d/%m')}"),
                        ("🗓️ Nghỉ tuần sau", f"{m_name} xin nghỉ tuần sau"),
                    ])
                    return jsonify({
                        'success': True,
                        'is_leave_intent': False,
                        'is_admin_mode': False,
                        'answer': (
                            f"❓ Bạn muốn đăng ký cho <strong>{m_name}</strong> xin nghỉ vào ngày nào vậy bạn?<br>"
                            f"👉 Bạn có thể nhắn ngày hoặc bấm chọn nhanh bên dưới:<br>"
                            f"<small style='color:#64748b;'>📌 Lưu ý: Không nhận đơn xin nghỉ Hôm nay và Ngày mai (được phép xin từ Ngày mốt). Nếu cần nghỉ gấp vui lòng liên hệ Admin.</small>{chips}"
                        ),
                        'engine': engine
                    })
                else:
                    chips = make_ai_chips([
                        ("⚡ Vinh nghỉ ngày mốt", "Vinh xin nghỉ ngày mốt việc bận"),
                        (f"👤 Bảo Mập nghỉ 2 ngày", f"Bảo Mập xin nghỉ 2 ngày từ {min_allowed_date.strftime('%d/%m')} khám bệnh"),
                        (f"👤 Thái nghỉ tuần sau", "Thái xin nghỉ tuần sau việc riêng"),
                    ])
                    return jsonify({
                        'success': True,
                        'is_leave_intent': False,
                        'is_admin_mode': False,
                        'answer': (
                            "❓ Bạn muốn đăng ký xin nghỉ cho ai và vào ngày nào vậy bạn?<br>"
                            "👉 Bạn có thể nhắn theo mẫu đầy đủ hoặc bấm chọn gợi ý bên dưới:<br>"
                            f"<small style='color:#64748b;'>📌 Lưu ý: Không nhận đơn xin nghỉ Hôm nay và Ngày mai (được phép xin từ Ngày mốt). Nếu cần nghỉ gấp vui lòng liên hệ Admin.</small>{chips}"
                        ),
                        'engine': engine
                    })

    # Nếu không phải báo nghỉ hoặc chỉ là câu hỏi tra cứu
    answer, engine = answer_schedule_query(question)
    return jsonify({
        'success': True,
        'question': question,
        'answer': answer,
        'engine': engine,
        'is_admin_mode': admin_mode
    })

@app.route('/api/ai-confirm-leave', methods=['POST'])
def api_ai_confirm_leave():
    """Tạo đơn xin nghỉ trực tiếp từ bong bóng chat AI (Hỗ trợ 1 ngày hoặc nhiều ngày liên tiếp)"""
    cleanup_and_advance_checkpoint()
    data = request.get_json(silent=True) or request.form
    member_name = (data.get('member_name') or '').strip()
    reason = (data.get('reason') or '').strip() or 'Việc cá nhân'
    created_at = get_vn_now().strftime('%Y-%m-%d %H:%M:%S')

    if member_name not in ALL_STAFF:
        return jsonify({'success': False, 'error': f'Nhân viên "{member_name}" không thuộc danh sách nhân sự.'})

    # Hỗ trợ nhận mảng leave_dates hoặc leave_date đơn lẻ
    leave_dates = data.get('leave_dates')
    if isinstance(leave_dates, str):
        try:
            leave_dates = json.loads(leave_dates)
        except Exception:
            leave_dates = [leave_dates]
    if not leave_dates:
        single_date = (data.get('leave_date') or '').strip()
        leave_dates = [single_date] if single_date else []

    today = get_vn_today()
    today_str = today.strftime('%Y-%m-%d')
    min_allowed_date = today + timedelta(days=2)
    min_allowed_str = min_allowed_date.strftime('%Y-%m-%d')

    # Chặn xin nghỉ cận ngày (Hôm nay, Ngày mai) nếu không phải Admin và không phải Nguyên
    if not is_admin() and member_name != 'Nguyên':
        invalid_near_dates = [d for d in leave_dates if d and today_str <= d < min_allowed_str]
        if invalid_near_dates:
            near_fmt = ', '.join([datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m/%Y') for d in invalid_near_dates])
            return jsonify({
                'success': False,
                'error': f'⛔ Không được phép xin nghỉ cận ngày ({near_fmt}). Trần Bình Auto không nhận đơn nghỉ Hôm nay và Ngày mai. Vui lòng liên hệ trực tiếp với Admin nếu có việc khẩn cấp!'
            })

    valid_dates = [d for d in leave_dates if d and d >= today_str]
    if not is_admin() and member_name != 'Nguyên':
        valid_dates = [d for d in valid_dates if d >= min_allowed_str]

    if not valid_dates:
        return jsonify({'success': False, 'error': 'Không có ngày xin nghỉ nào hợp lệ hoặc ngày đã qua.'})

    with get_db() as conn:
        for l_date in valid_dates:
            conn.execute('''
                INSERT INTO leaves (leave_date, member_name, reason, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(leave_date, member_name) DO UPDATE SET
                    reason = excluded.reason
            ''', (l_date, member_name, reason, created_at))
        conn.commit()

    actor_name = f"Admin ({member_name})" if is_admin() else member_name
    dates_desc = f"{len(valid_dates)} ngày ({', '.join(valid_dates)})" if len(valid_dates) > 1 else valid_dates[0]
    action_type = 'ADMIN DUYỆT NGHỈ' if is_admin() else 'XIN NGHỈ (AI CHAT)'
    log_action(action_type, f"{actor_name} đã xác nhận ca nghỉ {dates_desc} qua Trợ lý AI (Lý do: '{reason}')", actor='Admin' if is_admin() else member_name)

    return jsonify({
        'success': True,
        'member_name': member_name,
        'leave_dates': valid_dates,
        'reason': reason,
        'is_admin_mode': is_admin(),
        'message': f"{'Admin đã phê duyệt' if is_admin() else 'Đã ghi nhận'} thành công {len(valid_dates)} ngày nghỉ của {member_name}!"
    })

@app.route('/report-leave', methods=['POST'])
def report_leave():
    cleanup_and_advance_checkpoint()
    member_name = request.form.get('member_name')
    start_date_str = request.form.get('leave_date')
    end_date_str = request.form.get('end_date') or start_date_str
    reason = request.form.get('reason', '').strip() or 'Việc cá nhân'
    created_at = get_vn_now().strftime('%Y-%m-%d %H:%M:%S')
    
    today_dt = get_vn_today()
    today_str = today_dt.strftime('%Y-%m-%d')
    min_allowed_date = today_dt + timedelta(days=2)

    if start_date_str and member_name in ALL_STAFF:
        try:
            d_start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            d_end = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else d_start
            if d_end < d_start:
                d_start, d_end = d_end, d_start

            # Chặn xin nghỉ cận ngày (Hôm nay, Ngày mai) cho form thông thường (Ngoại lệ cho Nguyên)
            if not is_admin() and member_name != 'Nguyên' and d_start < min_allowed_date:
                log_action('TỪ CHỐI XIN NGHỈ CẬN', f"{member_name} bị từ chối xin nghỉ cận ngày ({d_start.strftime('%d/%m/%Y')})", actor=member_name)
                return redirect(url_for('index', tab='leaves'))
                
            num_days = (d_end - d_start).days + 1
            num_days = min(num_days, 31) # Giới hạn tối đa 31 ngày một lần
            
            with get_db() as conn:
                saved_count = 0
                for i in range(num_days):
                    cur_d = d_start + timedelta(days=i)
                    cur_str = cur_d.strftime('%Y-%m-%d')
                    if cur_str >= today_str:
                        conn.execute('''
                            INSERT INTO leaves (leave_date, member_name, reason, created_at)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(leave_date, member_name) DO UPDATE SET
                                reason = excluded.reason
                        ''', (cur_str, member_name, reason, created_at))
                        saved_count += 1
                conn.commit()
                
            actor_name = f"Admin ({member_name})" if is_admin() else member_name
            dates_info = f"từ {d_start.strftime('%d/%m/%Y')} đến {d_end.strftime('%d/%m/%Y')} ({saved_count} ngày)" if num_days > 1 else f"ngày {start_date_str}"
            log_action('XIN NGHỈ', f"{member_name} đăng ký xin nghỉ {dates_info} (Lý do: '{reason}')", actor=actor_name)
        except Exception:
            pass
            
    return redirect(url_for('index', tab='leaves'))

@app.route('/cancel-leave', methods=['POST'])
def cancel_leave():
    """Hủy đơn từ trang chủ: Kiểm tra giới hạn 15 phút hoặc Admin"""
    cleanup_and_advance_checkpoint()
    leave_date = request.form.get('leave_date')
    member_name = request.form.get('member_name')
    redirect_tab = request.form.get('tab', 'leaves')
    admin_mode = is_admin()
    
    if leave_date and member_name:
        with get_db() as conn:
            row = conn.execute('SELECT created_at FROM leaves WHERE leave_date = ? AND member_name = ?', (leave_date, member_name)).fetchone()
            if admin_mode:
                conn.execute('DELETE FROM leaves WHERE leave_date = ? AND member_name = ?', (leave_date, member_name))
                conn.commit()
                log_action('XÓA ĐƠN', f"Admin đã hủy ca nghỉ ngày {leave_date} của {member_name}", actor='Admin')
            elif row and row['created_at']:
                try:
                    c_dt = datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=VN_TZ)
                    diff_sec = (get_vn_now() - c_dt).total_seconds()
                    if diff_sec <= 900:  # Trong vòng 15 phút
                        conn.execute('DELETE FROM leaves WHERE leave_date = ? AND member_name = ?', (leave_date, member_name))
                        conn.commit()
                        log_action('HỦY ĐƠN (15P)', f"{member_name} tự hủy đơn nghỉ ngày {leave_date} (trong hạn 15 phút)", actor=member_name)
                    else:
                        log_action('HỦY THẤT BẠI', f"Cảnh báo: Có người cố hủy ca nghỉ ngày {leave_date} của {member_name} sau khi đã quá hạn 15 phút", actor='Nhân viên')
                except Exception:
                    pass
                    
    return redirect(url_for('index', tab=redirect_tab))

@app.route('/add-holiday', methods=['POST'])
def add_holiday():
    cleanup_and_advance_checkpoint()
    if not is_admin():
        log_action('CẢNH BÁO', 'Người dùng cố gắng cài đặt ngày tiệm đóng cửa khi chưa đăng nhập Admin', actor='Người dùng')
        return redirect(url_for('index', tab='schedule'))

    start_date_str = request.form.get('start_date') or request.form.get('holiday_date')
    end_date_str = request.form.get('end_date') or start_date_str
    reason = request.form.get('reason', '').strip() or 'Tiệm đóng cửa / Nghỉ lễ'
    
    if start_date_str:
        try:
            d_start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            d_end = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else d_start
            if d_end < d_start:
                d_start, d_end = d_end, d_start
                
            num_days = (d_end - d_start).days + 1
            with get_db() as conn:
                for i in range(num_days):
                    cur_d = d_start + timedelta(days=i)
                    cur_str = cur_d.strftime('%Y-%m-%d')
                    conn.execute('INSERT OR REPLACE INTO shop_holidays (holiday_date, reason) VALUES (?, ?)', 
                                 (cur_str, reason))
                conn.commit()
            log_action('CÀI ĐẶT NGHỈ TIỆM', f"Admin cài đặt tiệm đóng cửa từ {d_start.strftime('%d/%m/%Y')} đến {d_end.strftime('%d/%m/%Y')} ({num_days} ngày, lý do: '{reason}')", actor='Admin')
        except Exception:
            pass
            
    return redirect(url_for('index', tab='schedule'))

@app.route('/remove-holiday', methods=['POST'])
def remove_holiday():
    cleanup_and_advance_checkpoint()
    if not is_admin():
        log_action('CẢNH BÁO', 'Người dùng cố gắng xóa ngày tiệm đóng cửa khi chưa đăng nhập Admin', actor='Người dùng')
        return redirect(url_for('index', tab='schedule'))

    holiday_date = request.form.get('holiday_date')
    if holiday_date:
        with get_db() as conn:
            conn.execute('DELETE FROM shop_holidays WHERE holiday_date = ?', (holiday_date,))
            conn.commit()
        log_action('MỞ LẠI TIỆM', f"Admin mở lại hoạt động ngày {holiday_date}", actor='Admin')
    return redirect(url_for('index', tab='schedule'))

@app.route('/clear-all-holidays', methods=['POST'])
def clear_all_holidays():
    cleanup_and_advance_checkpoint()
    if not is_admin():
        log_action('CẢNH BÁO', 'Người dùng cố gắng xóa tất cả ngày tiệm đóng cửa khi chưa đăng nhập Admin', actor='Người dùng')
        return redirect(url_for('index', tab='schedule'))

    with get_db() as conn:
        count_row = conn.execute('SELECT COUNT(*) as cnt FROM shop_holidays').fetchone()
        cnt = count_row['cnt'] if count_row else 0
        conn.execute('DELETE FROM shop_holidays')
        conn.commit()
        
    log_action('XÓA TẤT CẢ NGHỈ TIỆM', f"Admin đã xóa toàn bộ {cnt} ngày đóng cửa của tiệm (mở lại toàn bộ lịch hoạt động)", actor='Admin')
    return redirect(url_for('index', tab='schedule'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
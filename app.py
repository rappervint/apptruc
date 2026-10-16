import os
import sqlite3
from datetime import datetime, timedelta, date, timezone
from flask import Flask, render_template, request, redirect, url_for, session, flash

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

# 8 người cố định trực nhật vệ sinh 7h30 sáng
DUTY_MEMBERS = ['Vinh', 'Dĩ', 'Ân', 'Bảo', 'Nguyên', 'Lợi', 'Thái', 'Duy']
# 2 nhân viên tại cửa hàng không trực nhật nhưng vẫn báo xin nghỉ bình thường
NON_DUTY_STAFF = ['Bảo Mập', 'Phát']
# Danh sách tất cả 10 nhân sự tại cửa hàng
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

    today_str = get_vn_today().strftime('%Y-%m-%d')
    today_leaves = [item for item in leaves_summary if item['leave_date'] == today_str]

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
                           holidays_list=holidays_list,
                           is_admin=is_admin())

@app.route('/history')
def history():
    """Trang tra cứu toàn bộ lịch sử xin nghỉ của cửa hàng"""
    cleanup_and_advance_checkpoint()
    
    selected_month = request.args.get('month', '')  # Định dạng YYYY-MM
    selected_member = request.args.get('member', '')
    today_str = get_vn_today().strftime('%Y-%m-%d')
    
    with get_db() as conn:
        # Lấy từ cả bảng lịch sử và bảng hiện hành
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
    
    available_months = set()
    history_list = []
    
    for r in rows:
        d_str = r['leave_date']
        m_str = d_str[:7]
        available_months.add(m_str)
        
        if selected_month and m_str != selected_month:
            continue
        if selected_member and r['member_name'] != selected_member:
            continue
            
        try:
            d_obj = datetime.strptime(d_str, '%Y-%m-%d').date()
            display_date = d_obj.strftime('%d/%m/%Y')
            weekday_str = weekday_vn.get(d_obj.strftime('%A'), d_obj.strftime('%A'))
            is_past = (d_str < today_str)
        except Exception:
            display_date = d_str
            weekday_str = ''
            is_past = False
            
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
            'month_str': m_str,
            'member_name': r['member_name'],
            'reason': r['reason'] or 'Việc cá nhân',
            'created_at': created_display,
            'is_duty_staff': is_duty_staff,
            'is_past': is_past,
            'source': r['source'],
            'can_cancel': can_cancel,
            'minutes_left': minutes_left
        })
        
    sorted_months = sorted(list(available_months), reverse=True)
    if not sorted_months:
        sorted_months = [get_vn_today().strftime('%Y-%m')]

    # Thống kê số ngày nghỉ theo từng nhân sự trong kết quả đã lọc
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
                           selected_month=selected_month,
                           selected_member=selected_member,
                           available_months=sorted_months,
                           all_staff=ALL_STAFF,
                           duty_members=DUTY_MEMBERS,
                           non_duty_staff=NON_DUTY_STAFF,
                           stats_by_member=stats_by_member,
                           total_leaves=len(history_list),
                           is_admin=is_admin(),
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

@app.route('/report-leave', methods=['POST'])
def report_leave():
    cleanup_and_advance_checkpoint()
    leave_date = request.form.get('leave_date')
    member_name = request.form.get('member_name')
    reason = request.form.get('reason', '').strip() or 'Việc cá nhân'
    created_at = get_vn_now().strftime('%Y-%m-%d %H:%M:%S')
    
    today_str = get_vn_today().strftime('%Y-%m-%d')
    if leave_date and leave_date >= today_str and member_name in ALL_STAFF:
        with get_db() as conn:
            conn.execute('''
                INSERT INTO leaves (leave_date, member_name, reason, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(leave_date, member_name) DO UPDATE SET
                    reason = excluded.reason
            ''', (leave_date, member_name, reason, created_at))
            conn.commit()
            
        actor_name = f"Admin ({member_name})" if is_admin() else member_name
        log_action('XIN NGHỈ', f"{member_name} đăng ký xin nghỉ ngày {leave_date} (Lý do: '{reason}')", actor=actor_name)
            
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
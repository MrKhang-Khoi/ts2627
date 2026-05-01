import re

with open('app.py', 'rb') as f:
    content = f.read()

# Find and replace the UPDATE block
old = (
    b"UPDATE students SET ho_ten=?, ho_ten_khong_dau=?, ngay_sinh=?,\r\n"
    b"                        lop=?, stt=?, note=?, updated_at=? WHERE id=?\"\"\",\r\n"
    b"                     (ho_ten, ho_ten_khong_dau, ngay_sinh, lop, stt, ghi_chu,\r\n"
    b"                      datetime.now().isoformat(), student_id))\r\n"
    b"        conn.commit()\r\n"
    b"        conn.close()\r\n"
)

new = (
    b"UPDATE students SET ho_ten=?, ho_ten_khong_dau=?, ngay_sinh=?,\r\n"
    b"                        lop=?, stt=?, note=?, cccd=?, ma_dinh_danh_gd=?, updated_at=? WHERE id=?\"\"\",\r\n"
    b"                     (ho_ten, ho_ten_khong_dau, ngay_sinh, lop, stt, ghi_chu,\r\n"
    b"                      cccd or None, ma_dinh_danh_gd or None,\r\n"
    b"                      datetime.now().isoformat(), student_id))\r\n"
    b"        conn.commit()\r\n"
    b"        conn.close()\r\n"
)

if old in content:
    content2 = content.replace(old, new, 1)
    with open('app.py', 'wb') as f:
        f.write(content2)
    print('THANH CONG: Da cap nhat SQL edit-student')
else:
    # Debug: show what's there
    idx = content.find(b'UPDATE students SET ho_ten=')
    print('KHONG KHOP. Noi dung hien tai:')
    print(repr(content[idx:idx+350]))

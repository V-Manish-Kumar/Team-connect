use flask_login;
CREATE TABLE error_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME,
    error_message TEXT,
    stack_trace TEXT,
    endpoint VARCHAR(255),
    admin_id INT,
    FOREIGN KEY (admin_id) REFERENCES admin_users(id)
);

INSERT INTO error_logs (timestamp, error_message, stack_trace, endpoint, admin_id)
VALUES (
    '2025-03-03 10:15:23',
    'User registration failed: Duplicate entry \'user@example.com\' for key \'email\'',
    'Traceback (most recent call last):\n  File "/app/routes.py", line 123, in register\n    cur.execute("INSERT INTO users ...")\n  File "/usr/lib/python3.9/mysql/connector/cursor.py", line 123, in execute\n    raise IntegrityError\nmysql.connector.errors.IntegrityError: Duplicate entry \'user@example.com\' for key \'email\'',
    '/register',
    NULL
);

INSERT INTO error_logs (timestamp, error_message, stack_trace, endpoint, admin_id)
VALUES (
    '2025-03-03 14:30:45',
    'Admin login failed: Can\'t connect to MySQL server on \'localhost\' (10061)',
    'Traceback (most recent call last):\n  File "/app/routes.py", line 89, in admin_login\n    cur = mysql.connection.cursor()\n  File "/usr/lib/python3.9/mysql/connector/connection.py", line 456, in cursor\n    self._connection.connect()\n  File "/usr/lib/python3.9/mysql/connector/connection.py", line 123, in connect\n    raise DatabaseError\nmysql.connector.errors.DatabaseError: 2003: Can\'t connect to MySQL server on \'localhost\' (10061)',
    '/admin/login',
    NULL
);

INSERT INTO error_logs (timestamp, error_message, stack_trace, endpoint, admin_id)
VALUES (
    '2025-03-03 16:22:10',
    'File upload failed: [Errno 13] Permission denied: \'file_uploads/20250303_162210_document.pdf\'',
    'Traceback (most recent call last):\n  File "/app/routes.py", line 456, in upload_file\n    file.save(file_path)\n  File "/usr/lib/python3.9/werkzeug/datastructures.py", line 123, in save\n    with open(destination, \'wb\') as f:\nPermissionError: [Errno 13] Permission denied: \'file_uploads/20250303_162210_document.pdf\'',
    '/upload',
    1
);

INSERT INTO error_logs (timestamp, error_message, stack_trace, endpoint, admin_id)
VALUES (
    '2025-03-03 11:45:33',
    'Chat room creation failed: Duplicate entry \'Room123\' for key \'name\'',
    'Traceback (most recent call last):\n  File "/app/routes.py", line 300, in create_room\n    cur.execute("INSERT INTO chat_rooms (name, created_by) VALUES (%s, %s)", (room_name, current_user.id))\n  File "/usr/lib/python3.9/mysql/connector/cursor.py", line 123, in execute\n    raise IntegrityError\nmysql.connector.errors.IntegrityError: Duplicate entry \'Room123\' for key \'name\'',
    '/create_room',
    2
);

select * from error_logs;

import face_recognition
import cv2
import numpy as np
import sqlite3
from datetime import datetime
import csv
import os
import pyttsx3
tts = pyttsx3.init()

# Connect to SQLite database
conn = sqlite3.connect('Attendance.db')
cursor = conn.cursor()

now = datetime.now()
current_date = now.strftime("table_%Y_%m_%d")

# Table name for current date
table_name = "" + current_date

# Create table if not exists with Roll No column
cursor.execute('''CREATE TABLE IF NOT EXISTS {} 
                (Name TEXT, RollNo INTEGER, Year TEXT, Division TEXT, Time TEXT, Status TEXT)'''.format(table_name))

# Function to read student information from a CSV file
def read_student_info_from_csv(filename):
    student_info = []
    with open(filename, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            student_info.append(row)
    return student_info

# Read student information from CSV
students_info = read_student_info_from_csv('students.csv')

# Mapping student names to their roll numbers
student_roll_mapping = {student["name"]: {"roll_no": int(student["roll_no"]), "year": student["year"], "division": student["division"]} for student in students_info}
name_list=[student["name"] for student in students_info]

video_capture = cv2.VideoCapture(0)

# Load images and encodings for known faces
known_face_encodings = []
known_faces_names = []

for student in students_info:
    student_name = student["name"]
    for extension in ["jpg", "jpeg",'png']:
        image_path = f"photos/{student_name}.{extension}"
        if os.path.exists(image_path):
            image = face_recognition.load_image_file(image_path)
            face_encodings = face_recognition.face_encodings(image)
            if len(face_encodings) > 0:  # Check if any face encodings were found
                encoding = face_encodings[0]
                # Dynamically create variable name for student's encoding
                globals()[f"{student_name}_encoding"] = encoding
                # Store variable name in known_face_encodings list
                known_face_encodings.append(globals()[f"{student_name}_encoding"])
                known_faces_names.append(student_name)
                # print("ROll no added:- {}",student["roll_no"])
            else:
                print(f"No face found in {image_path}")
            break  # Break the loop if image is successfully loaded


present_students = []


# Write remaining students as absent
def write_absent_students(students):
    for remaining_student in students:
        update_or_insert_attendance(remaining_student, student_roll_mapping[remaining_student]["roll_no"], student_roll_mapping[remaining_student]["year"], student_roll_mapping[remaining_student]["division"], 'Absent', "-")

# Function to update or insert attendance records
def update_or_insert_attendance(name, roll_no, year, division, status, time):
    if time == "-":
        cursor.execute("SELECT * FROM {} WHERE Name=?".format(table_name), (name,))
        existing_record = cursor.fetchone()
        if existing_record:
            cursor.execute("UPDATE {} SET Status=? WHERE Name=?" .format(table_name),(status, name))
        else:
            cursor.execute("INSERT INTO {} (Name, RollNo, Year, Division, Time, Status) VALUES (?, ?, ?, ?, ?, ?)".format(table_name), (name, roll_no, year, division, time, status))
    else:
        current_time = datetime.now().strftime("%H-%M-%S")
        cursor.execute("SELECT * FROM {} WHERE Name=?".format(table_name), (name,))
        existing_record = cursor.fetchone()
        if existing_record:
            cursor.execute("UPDATE {} SET Time=?, Status=? WHERE Name=?" .format(table_name),(current_time, status, name))
        else:
            cursor.execute("INSERT INTO {} (Name, RollNo, Year, Division, Time, Status) VALUES (?, ?, ?, ?, ?, ?)".format(table_name), (name, roll_no, year, division, current_time, status))
    conn.commit()

while True:
    _, frame = video_capture.read()
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = small_frame[:, :, ::-1]

    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
    face_names = []

    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        name = ""
        face_distance = face_recognition.face_distance(known_face_encodings, face_encoding)
        best_match_index = np.argmin(face_distance)
        if matches[best_match_index]:
            name = known_faces_names[best_match_index]
            face_names.append(name)

            if name not in present_students:
                current_time = datetime.now().strftime("%H-%M-%S")
                cursor.execute("SELECT * FROM {} WHERE Name=?".format(table_name), (name,))
                existing_record = cursor.fetchone()
                if existing_record is not None:
                    status = existing_record[5]
                    if status == 'Present':
                        message = name + ' Already marked'
            
                    else:
                        message = name + ' Present'
                        present_students.append(name)
                        current_time = datetime.now().strftime("%H-%M-%S")
                        print(present_students)
                        update_or_insert_attendance(name, student_roll_mapping[name]["roll_no"], student_roll_mapping[name]["year"], student_roll_mapping[name]["division"], 'Present', current_time)
                else:
                    message = name + ' Present'
                    present_students.append(name)
                    current_time = datetime.now().strftime("%H-%M-%S")
                    print(present_students)
                    current_time = datetime.now().strftime("%H-%M-%S")
                    update_or_insert_attendance(name, student_roll_mapping[name]["roll_no"], student_roll_mapping[name]["year"], student_roll_mapping[name]["division"], 'Present', current_time)

                # cv2.putText(frame, message,
                #             (10, 100),
                #             cv2.FONT_HERSHEY_SIMPLEX,
                #             1.5,
                #             (255, 0, 0),
                #             3,
                #             2)
            tts.say(message)
            tts.runAndWait()
            cv2.waitKey(2000)

    cv2.imshow("Attendance system", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cursor.execute("SELECT Name FROM {} WHERE Status='Present'".format(table_name))
present_db_records = cursor.fetchall()

# Extract names from the fetched records
present_db = [record[0] for record in present_db_records]

absent=set(name_list)-set(present_db)
write_absent_students(absent)
# Close SQLite connection
conn.close()

video_capture.release()
cv2.destroyAllWindows()
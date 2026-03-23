import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import Calendar
from datetime import datetime
import sys
import os

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class VacationDatabase:
    def __init__(self, db_name="vacation_records.db"):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS employees 
                          (id INTEGER PRIMARY KEY, name TEXT UNIQUE, total_days INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS vacations 
                          (id INTEGER PRIMARY KEY, employee_id INTEGER, 
                           vacation_date TEXT, reason TEXT,
                           FOREIGN KEY(employee_id) REFERENCES employees(id))''')
        self.conn.commit()

    def delete_date(self, employee_name, date_obj):
        cursor = self.conn.cursor()
        date_str = date_obj.strftime('%Y-%m-%d')
        cursor.execute("SELECT id FROM employees WHERE name=?", (employee_name,))
        res = cursor.fetchone()
        if res:
            employee_id = res[0]
            cursor.execute("DELETE FROM vacations WHERE employee_id = ? AND vacation_date = ?",
                           (employee_id, date_str))
            self.conn.commit()

    def add_employee(self, name, total):
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO employees (name, total_days) VALUES (?, ?)", (name, total))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_employees(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM employees")
        return [row[0] for row in cursor.fetchall()]

    def delete_employee(self, name):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM vacations WHERE employee_id = (SELECT id FROM employees WHERE name=?)", (name,))
        cursor.execute("DELETE FROM employees WHERE name=?", (name,))
        self.conn.commit()

    def book_date(self, employee_name, date_obj, reason):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM employees WHERE name=?", (employee_name,))
        result = cursor.fetchone()
        if result:
            employee_id = result[0]
            date_str = date_obj.strftime('%Y-%m-%d')
            cursor.execute("INSERT INTO vacations (employee_id, vacation_date, reason) VALUES (?, ?, ?)",
                           (employee_id, date_str, reason))
            self.conn.commit()

    def get_all_dates(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT vacation_date FROM vacations")
        return [datetime.strptime(row[0], '%Y-%m-%d').date() for row in cursor.fetchall()]

    def details_for_date(self, date_obj):
        cursor = self.conn.cursor()
        date_str = date_obj.strftime('%Y-%m-%d')
        cursor.execute('''SELECT employees.name, vacations.reason FROM vacations 
                          JOIN employees ON vacations.employee_id = employees.id 
                          WHERE vacations.vacation_date = ?''', (date_str,))
        return cursor.fetchall()

    def get_statistics(self, employee_name):
        cursor = self.conn.cursor()
        cursor.execute("SELECT total_days FROM employees WHERE name=?", (employee_name,))
        res = cursor.fetchone()
        if not res: return 0, 0
        total = res[0]
        cursor.execute('''SELECT COUNT(*) FROM vacations 
                          JOIN employees ON vacations.employee_id = employees.id 
                          WHERE employees.name = ?''', (employee_name,))
        used = cursor.fetchone()[0]
        return total, used


class VacationApp:
    def __init__(self, root):
        self.db = VacationDatabase()
        self.root = root
        self.root.title("Vacation Leave Planner")
        self.root.geometry("1000x750")

        try:
            self.root.iconbitmap(resource_path("group.ico"))
        except:
            pass

        self.setup_ui()
        self.refresh_calendar()
        self.load_employees()

    def setup_ui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(self.root, padding="15")
        left_frame.grid(row=0, column=0, sticky="ns")

        ttk.Label(left_frame, text="Add New Employee", font=("Arial", 10, "bold")).pack(pady=5)
        self.name_ent = ttk.Entry(left_frame, width=25)
        self.name_ent.pack(pady=2)
        self.name_ent.insert(0, "Full Name")

        self.days_ent = ttk.Entry(left_frame, width=10)
        self.days_ent.insert(0, "21")
        self.days_ent.pack(pady=2)

        ttk.Button(left_frame, text="Add Employee", command=self.ui_add_employee).pack(fill="x", pady=5)

        ttk.Label(left_frame, text="Employee List:").pack(anchor="w", pady=(10, 0))
        self.employee_lb = tk.Listbox(left_frame, height=15, font=("Arial", 10))
        self.employee_lb.pack(fill="both", expand=True, pady=5)
        self.employee_lb.bind('<<ListboxSelect>>', lambda e: self.update_info())

        ttk.Button(left_frame, text="Delete Selected", command=self.ui_delete_employee).pack(fill="x", pady=5)
        self.info_lbl = ttk.Label(left_frame, text="Select employee for details", foreground="blue")
        self.info_lbl.pack(pady=10)

        right_frame = ttk.Frame(self.root, padding="15")
        right_frame.grid(row=0, column=1, sticky="nsew")

        ttk.Label(right_frame, text="Vacation Calendar (Click for details)", font=("Arial", 11)).pack()

        self.cal = Calendar(right_frame, selectmode='day', font="Arial 14",
                            headersbackground="#2c3e50", headersforeground="white",
                            locale='en_US')
        self.cal.pack(pady=10, fill="both", expand=True)
        self.cal.bind("<<CalendarSelected>>", self.show_details)

        self.details_text = tk.Text(right_frame, height=5, font=("Arial", 10), bg="#f9f9f9")
        self.details_text.pack(fill="x", pady=5)
        self.details_text.insert("1.0", "Click on a date to see who is on leave...")

        book_frame = ttk.LabelFrame(right_frame, text="Enter Vacation", padding="10")
        book_frame.pack(fill="x", pady=10)

        ttk.Label(book_frame, text="Reason:").grid(row=0, column=0, padx=5)
        self.reason_ent = ttk.Entry(book_frame)
        self.reason_ent.grid(row=0, column=1, padx=5, sticky="ew")
        book_frame.columnconfigure(1, weight=1)

        ttk.Button(book_frame, text="Delete for this employee", command=self.ui_remove_date).grid(row=0, column=3, padx=10)
        ttk.Button(book_frame, text="Confirm Absence", command=self.ui_book).grid(row=0, column=2, padx=10)

    def load_employees(self):
        self.employee_lb.delete(0, tk.END)
        for name in self.db.get_employees():
            self.employee_lb.insert(tk.END, name)

    def ui_add_employee(self):
        name = self.name_ent.get()
        days = self.days_ent.get()
        if name and days.isdigit():
            if self.db.add_employee(name, int(days)):
                self.load_employees()
                self.name_ent.delete(0, tk.END)
            else:
                messagebox.showerror("Error", "Employee already exists in database.")

    def ui_delete_employee(self):
        sel = self.employee_lb.curselection()
        if sel:
            name = self.employee_lb.get(sel)
            if messagebox.askyesno("Confirmation", f"Are you sure you want to delete employee: {name}?"):
                self.db.delete_employee(name)
                self.load_employees()
                self.refresh_calendar()

    def update_info(self):
        sel = self.employee_lb.curselection()
        if sel:
            name = self.employee_lb.get(sel)
            total, used = self.db.get_statistics(name)
            remaining = total - used
            self.info_lbl.config(text=f"{name}:\n{used}/{total} used\nRemaining: {remaining}")

    def refresh_calendar(self):
        self.cal.calevent_remove('all')
        all_dates = self.db.get_all_dates()
        for d in all_dates:
            self.cal.calevent_create(d, 'Vacation', 'vacation')
        self.cal.tag_config('vacation', background='#e74c3c', foreground='white')

    def ui_book(self):
        sel = self.employee_lb.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Please select an employee from the list first!")
            return

        name = self.employee_lb.get(sel)
        date = self.cal.selection_get()
        reason = self.reason_ent.get()

        self.db.book_date(name, date, reason)
        self.refresh_calendar()
        self.update_info()
        self.show_details(None)
        self.reason_ent.delete(0, tk.END)

    def ui_remove_date(self):
        sel = self.employee_lb.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Please select an employee from the list first!")
            return

        name = self.employee_lb.get(sel)
        date = self.cal.selection_get()

        if messagebox.askyesno("Confirmation", f"Delete vacation for {name} on {date}?"):
            self.db.delete_date(name, date)
            self.refresh_calendar()
            self.update_info()
            self.show_details(None)

    def show_details(self, event):
        date = self.cal.selection_get()
        details = self.db.details_for_date(date)

        self.details_text.delete("1.0", tk.END)
        if not details:
            self.details_text.insert("1.0", f"Date: {date}\nNo vacations scheduled.")
            return

        self.details_text.insert("1.0", f"Date: {date}\n")
        for name, reason in details:
            self.details_text.insert(tk.END, f"• {name} (Reason: {reason})\n")


if __name__ == "__main__":
    root = tk.Tk()
    app = VacationApp(root)
    root.mainloop()
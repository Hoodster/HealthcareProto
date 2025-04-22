import tkinter as tk
from tkinter import messagebox, scrolledtext
import json
import os


class SimpleAnnotator:
    def __init__(self, master, sentences, categories):
        self.master = master
        self.master.title("ESC Guidelines Annotator")
        self.master.geometry("900x700")

        self.sentences = sentences
        self.current_idx = 0
        self.categories = categories
        self.annotations = {}

        # Create UI elements
        self.create_widgets()
        self.display_current_sentence()

    def create_widgets(self):
        # Text display
        self.text_frame = tk.Frame(self.master)
        self.text_frame.pack(pady=10, fill=tk.BOTH, expand=True)

        self.text_display = scrolledtext.ScrolledText(self.text_frame, wrap=tk.WORD, width=80, height=10)
        self.text_display.pack(fill=tk.BOTH, expand=True)

        # Category buttons
        self.button_frame = tk.Frame(self.master)
        self.button_frame.pack(pady=10)

        self.category_var = tk.StringVar()
        self.category_var.set("none")

        for category in ["none"] + self.categories:
            rb = tk.Radiobutton(self.button_frame, text=category, variable=self.category_var, value=category)
            rb.pack(side=tk.LEFT, padx=5)

        # Navigation buttons
        self.nav_frame = tk.Frame(self.master)
        self.nav_frame.pack(pady=10)

        self.prev_btn = tk.Button(self.nav_frame, text="Previous", command=self.prev_sentence)
        self.prev_btn.pack(side=tk.LEFT, padx=5)

        self.next_btn = tk.Button(self.nav_frame, text="Next", command=self.next_sentence)
        self.next_btn.pack(side=tk.LEFT, padx=5)

        self.save_btn = tk.Button(self.nav_frame, text="Save", command=self.save_annotations)
        self.save_btn.pack(side=tk.LEFT, padx=20)

        # Progress indicator
        self.progress_label = tk.Label(self.master, text="")
        self.progress_label.pack(pady=10)

    def display_current_sentence(self):
        if 0 <= self.current_idx < len(self.sentences):
            self.text_display.delete(1.0, tk.END)
            self.text_display.insert(tk.END, self.sentences[self.current_idx])

            # Set the category if already annotated
            if self.current_idx in self.annotations:
                self.category_var.set(self.annotations[self.current_idx])
            else:
                self.category_var.set("none")

            self.progress_label.config(text=f"Sentence {self.current_idx + 1} of {len(self.sentences)}")

    def next_sentence(self):
        # Save current annotation
        if self.category_var.get() != "none":
            self.annotations[self.current_idx] = self.category_var.get()
        elif self.current_idx in self.annotations:
            del self.annotations[self.current_idx]

        # Move to next
        if self.current_idx < len(self.sentences) - 1:
            self.current_idx += 1
            self.display_current_sentence()

    def prev_sentence(self):
        # Save current annotation
        if self.category_var.get() != "none":
            self.annotations[self.current_idx] = self.category_var.get()
        elif self.current_idx in self.annotations:
            del self.annotations[self.current_idx]

        # Move to previous
        if self.current_idx > 0:
            self.current_idx -= 1
            self.display_current_sentence()

    def save_annotations(self):
        # Create annotated dataset
        dataset = []
        for idx, sentence in enumerate(self.sentences):
            if idx in self.annotations:
                dataset.append({
                    "text": sentence,
                    "label": self.annotations[idx]
                })

        # Save to file
        with open("annotated_af_guidelines.json", 'w', encoding='utf-8') as file:
            json.dump(dataset, file, ensure_ascii=False, indent=2)

        messagebox.showinfo("Success", f"Saved {len(dataset)} annotated sentences.")


# Categories for AF drug safety monitoring
categories = [
    "anticoagulation_monitoring",
    "antiarrhythmic_monitoring",
    "rate_control_monitoring",
    "follow_up_protocol",
    "drug_interaction",
    "adverse_events",
    "other_safety"
]

# Usage (uncomment to run)
# with open("cleaned_guidelines.txt", 'r', encoding='utf-8') as file:
#     text = file.read()
#     sentences = sent_tokenize(text)
#
# root = tk.Tk()
# app = SimpleAnnotator(root, sentences, categories)
# root.mainloop()
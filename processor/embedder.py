import openai
import fitz  # PyMuPDF
import io
from PIL import Image
import base64


class Embedder:
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)

    def _get_image_caption(self, page, img_rect):
        """
        A simple heuristic to find a caption for an image.
        Looks for text blocks below the image.
        """
        caption = ""
        blocks = page.get_text("dict", flags=0)["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        span_rect = fitz.Rect(span["bbox"])
                        # Check if the text is below the image and close to it
                        if span_rect.y0 > img_rect.y1 and abs(span_rect.y0 - img_rect.y1) < 50:
                             if span["text"].strip().lower().startswith("figure") or span["text"].strip().lower().startswith("chart"):
                                caption += span["text"].strip() + " "
        return caption.strip()

    def process_document(self, file_path):
        doc = fitz.open(file_path)
        results = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()  # type: ignore[attr-defined]
            images = page.get_images(full=True)

            page_content = {"page": page_num + 1, "text": text, "images": []}

            for img_index, img in enumerate(images):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]

                # Get image caption
                img_rect = page.get_image_bbox(img)
                caption = self._get_image_caption(page, img_rect)

                # Encode image to base64
                base64_image = base64.b64encode(image_bytes).decode('utf-8')

                page_content["images"].append({
                    "caption": caption if caption else "No caption found.",
                    "base64_image": base64_image
                })

            results.append(page_content)

        return results

    def get_embeddings(self, processed_content):
        embeddings = []
        for content in processed_content:
            # Embed text
            if content["text"]:
                response = self.client.embeddings.create(
                    input=content["text"],
                    model="text-embedding-3-small" # Or another suitable model
                )
                embeddings.append({
                    "page": content["page"],
                    "type": "text",
                    "embedding": response.data[0].embedding
                })

            # For images, we will embed the caption for now.
            # For a more advanced solution, a multimodal embedding model would be needed.
            for img_content in content["images"]:
                if img_content["caption"]:
                    response = self.client.embeddings.create(
                        input=img_content["caption"],
                        model="text-embedding-3-small"
                    )
                    embeddings.append({
                        "page": content["page"],
                        "type": "image_caption",
                        "embedding": response.data[0].embedding
                    })
        return embeddings

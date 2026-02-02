"""Text-based chart types: wordcloud."""

from typing import List, Dict, Optional
import matplotlib.pyplot as plt


def render_wordcloud_chart(
    sessions: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a wordcloud from session notes."""
    try:
        from wordcloud import WordCloud
    except ImportError:
        print("Error: wordcloud library is required for wordcloud charts.")
        print("Install it with: pip install wordcloud")
        return

    if not sessions:
        print("No data to display.")
        return

    # Extract notes from sessions
    notes_text = " ".join([s.get("note", "") or "" for s in sessions if s.get("note")])

    if not notes_text.strip():
        print("No notes found in sessions.")
        return

    # Create wordcloud
    wordcloud = WordCloud(
        width=800,
        height=400,
        background_color="white",
        max_words=100,
        colormap="viridis",
    ).generate(notes_text)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(
        title or "Session Notes Wordcloud", fontsize=14, fontweight="bold", pad=20
    )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()

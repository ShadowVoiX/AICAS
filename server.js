import express from "express";
import cors from "cors";
import dotenv from "dotenv";

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

app.post("/chat", async (req, res) => {
    try {
        const userMessage = req.body.message;

        const response = await fetch(
            `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${GEMINI_API_KEY}`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    contents: [
                        {
                            parts: [
                                {
                                    text: `You are a helpful student assistant chatbot.\nUser: ${userMessage}`
                                }
                            ]
                        }
                    ]
                })
            }
        );

        const data = await response.json();

        const reply =
            data.candidates?.[0]?.content?.parts?.[0]?.text ||
            "Sorry, I couldn't respond.";

        res.json({ reply });

    } catch (error) {
        console.error(error);
        res.status(500).json({ reply: "Error connecting to Gemini" });
    }
});

app.listen(3000, () => {
    console.log("Server running on http://localhost:3000");
});
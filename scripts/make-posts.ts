// node scripts/make-post.ts "Title Here" 2020-07-01 corpus/youtube/clean/2020-qgis-gee-plugin-part-1.md
import fs from "node:fs";
import path from "node:path";
import OpenAI from "openai";

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY! });
const [,, titleArg, dateArg, srcArg] = process.argv;

if (!titleArg || !dateArg || !srcArg) {
  console.error("Usage: node scripts/make-post.ts \"Title\" YYYY-MM-DD path/to/clean.md");
  process.exit(1);
}

const title = titleArg;
const date  = dateArg;
const notes = fs.readFileSync(srcArg, "utf8");
const voice = fs.readFileSync("prompts/VOICE_GUIDE.md", "utf8");

// small helper
async function ask(system: string, user: string) {
  const res = await openai.responses.create({
    model: "gpt-4o-mini", // fast & cheap; swap later to your fine-tuned
    input: [
      { role: "system", content: system },
      { role: "user", content: user }
    ],
  });
  // Grab the first text block
  // @ts-ignore
  return res.output_text ?? res.output?.[0]?.content?.[0]?.text ?? "";
}

(async () => {
  const mdx = await ask(
    "You are Brandon Crosbie’s writing partner. Output only valid MDX.",
    `VOICE_GUIDE:\n${voice}\n\nCreate a 1200–1600 word MDX blog post with frontmatter:\n---\ntitle: "${title}"\ndate: "${date}"\nexcerpt: (one sentence)\ntags: [geospatial, google-earth-engine, qgis]\nhero: "/images/blog/gee-qgis.png"\n---\n\nGround your claims ONLY in the SOURCE below. Use H2/H3 headings, include short callouts and code blocks where useful. No JSX components, just MDX.\n\nSOURCE:\n${notes}`
  );

  const summary = await ask(
    "Summarize for social drafting.",
    `Give 4–6 bullets (max ~600 chars total) of the key takeaways from this MDX:\n${mdx.slice(0, 6000)}`
  );

  const linkedin = await ask(
    "You are Brandon writing for LinkedIn.",
    `VOICE_GUIDE:\n${voice}\n\nWrite a 900–1100 character LinkedIn post teeing up the blog "${title}". Use the bullets verbatim where possible.\nStructure: 1 strong hook line, 2–3 short paragraphs, 1 skim list, clear CTA to read the blog. No more than 3 hashtags at the end.\nBULLETS:\n${summary}`
  );

  const xpost = await ask(
    "You are Brandon posting to X.",
    `VOICE_GUIDE:\n${voice}\n\nWrite 1 post ≤ 260 chars, punchy, one insight + CTA about "${title}". No hashtags.`
  );

  const slug = `${date}-${title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/(^-|-$)/g,"")}`;

  fs.mkdirSync("blog", { recursive: true });
  fs.mkdirSync("social", { recursive: true });
  fs.writeFileSync(path.join("blog", `${slug}.mdx`), mdx.trim()+"\n", "utf8");
  fs.writeFileSync(path.join("social", `${slug}.linkedin.txt`), linkedin.trim()+"\n", "utf8");
  fs.writeFileSync(path.join("social", `${slug}.x.txt`), xpost.trim()+"\n", "utf8");

  console.log("Wrote:");
  console.log(`  blog/${slug}.mdx`);
  console.log(`  social/${slug}.linkedin.txt`);
  console.log(`  social/${slug}.x.txt`);
})();

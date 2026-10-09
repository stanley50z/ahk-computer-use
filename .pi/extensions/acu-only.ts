// Inside this repository ACU is the computer-use skill. This project extension removes the user-level
// cua-driver skill from the system prompt so the two never compete here. Pi offers no settings-level
// switch for hiding a user skill in one project, which is why this is code.
import { formatSkillsForPrompt, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

const HIDDEN_SKILLS = new Set(["cua-driver"]);

export default function (pi: ExtensionAPI) {
  pi.on("before_agent_start", (event) => {
    const skills = event.systemPromptOptions.skills;
    if (!skills) return;
    const kept = skills.filter((skill) => !HIDDEN_SKILLS.has(skill.name));
    if (kept.length === skills.length) return;
    const originalBlock = formatSkillsForPrompt(skills);
    event.systemPromptOptions.skills = kept;
    return {
      systemPrompt: originalBlock ? event.systemPrompt.replace(originalBlock, formatSkillsForPrompt(kept)) : event.systemPrompt,
    };
  });
}

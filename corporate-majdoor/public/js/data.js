/** Static content: boss lines, stickies, sprint tickets, fake code, share links. */

export const BOSS_LINES = [
  { face: '🤬', text: 'Kaha ho tum?! PPT deck kab aayegi?! Client presentation 2 minute me start ho rahi hai!' },
  { face: '😡', text: 'Ye kya bheja hai?! Font size 11 bola tha, tumne 12 kar diya. Redo the whole deck.' },
  { face: '🙄', text: 'Weekend pe thoda sa kaam hai bas… 2-3 ghante ka. Monday morning tak chahiye.' },
  { face: '😤', text: 'Standup me camera on karo. Team bonding important hai, output baad me dekhenge.' },
  { face: '🤨', text: 'Teams pe yellow dikh rahe the 4 minute. Chai itni lambi kyun hoti hai?' },
  { face: '😠', text: 'Appraisal cycle tough hai is saal. But you got "Meets Expectations" — congratulations!' },
  { face: '🧐', text: 'Quick call? 2 minute ka hai.' , sub: '(47 minutes later…)' },
  { face: '😒', text: 'Production down hai aur tum lunch pe ho? Priorities set karo yaar.' },
  { face: '🤬', text: 'Ye estimate 5 din ka kaise? Client ko 2 din bol diya hai maine. Manage kar lo.' },
  { face: '😬', text: 'Resource crunch hai. Tum hi do teams handle kar lo, visibility milegi.' },
  { face: '😐', text: 'WFH policy revise ho gayi. Kal se 5 days office, 60 km ka commute manageable hai.' },
  { face: '😤', text: 'Timesheet fill nahi kiya! 8 ghante kaam, 2 ghante timesheet — simple hai.' },
  { face: '🤯', text: 'Client ne scope change kiya hai. Deadline wahi rahegi. Sprint ho jayega na?' },
  { face: '😇', text: 'We are like a family here. Family ke liye Sunday deploy to kar sakte ho?' },
  { face: '🫠', text: 'Hike 4% hai. Inflation 6% hai. But learning opportunity infinite hai!' },
];

export const BOSS_REPLIES = [
  '"Working on it Sir! 🙏"',
  '"Just pushing the final commit Sir 🙏"',
  '"Almost done Sir, testing chal raha hai 🙏"',
  '"Yes Sir, circling back on it 🙏"',
  '"Sir network issue tha, ab theek hai 🙏"',
];

export const DEFAULT_STICKIES = [
  {
    id: 'agenda',
    title: 'Meeting Notes ✍️',
    color: '#ffe066',
    x: 40,
    y: 40,
    text:
      '1. Nodding like I understand everything\n' +
      '2. Keeping Teams status active (green)\n' +
      '3. Planning 5:00 PM tapri chai break\n' +
      '4. "Let\'s circle back on this offline"\n' +
      '5. Appraisal form me kya likhu? 😭',
  },
  {
    id: 'math',
    title: 'Monthly Majdoor Math 💸',
    color: '#ffd6a5',
    x: 320,
    y: 120,
    text:
      '• In-Hand: ₹40,000\n' +
      '• Room Rent: -₹18,000\n' +
      '• Chai & Sutta: -₹4,000\n' +
      '• Swiggy / Zomato: -₹6,000\n' +
      '• Credit Card EMI: -₹14,000\n' +
      '• Net Savings: -₹2,000 😭',
  },
  {
    id: 'townhall',
    title: 'All-Hands Townhall 💀',
    color: '#caffbf',
    x: 610,
    y: 60,
    text: 'Why am I here?\n\nMood: "Kal se resign"\n\nCEO: "We are a rocket ship 🚀"\nMe: "Where is my seat?"',
  },
  {
    id: 'resign',
    title: 'Resignation Letter Draft 📜',
    color: '#bdb2ff',
    x: 880,
    y: 180,
    text:
      '"Dear Manager,\n\nPlease accept this as formal notice\nthat I want to sleep 8 hours daily.\n\nWarm regards,\nTired Majdoor"',
  },
];

export const STICKY_COLORS = ['#ffe066', '#ffd6a5', '#caffbf', '#bdb2ff', '#9bf6ff', '#ffadad'];

export const JIRA_TICKETS = [
  '⏳ CORP-4921: Fix production memory leak',
  '🔥 CORP-4930: Client escalation — "make it pop"',
  '📦 CORP-4888: Migrate legacy batch job',
  '🧪 CORP-4902: Add tests (moved 6 sprints)',
  '💤 CORP-4777: Reduce meeting hours (won\'t fix)',
];

export const FAKE_CODE = `/** CRITICAL HOTFIX FOR HIGH-PRIORITY CLIENT TICKET — CORP-4921 */
package com.techpark.corporate.engine;

import com.techpark.corporate.chai.ChaiBreakScheduler;
import com.techpark.corporate.hr.AppraisalDenialStrategy;

public class PaymentGatewayService implements HighPriorityService {

    private final ClientSyncOrchestrator orchestrator;
    private final ChaiBreakScheduler chaiScheduler;
    private volatile boolean isOvertimeActive = true;

    /** Process all incoming backlog transactions before EOD. */
    public synchronized void executeCriticalPipeline(ExecutionContext ctx) {
        if (ctx.getStressLevel() > 9000) {
            log.warn("Chai break required immediately.");
            this.chaiScheduler.triggerEmergencyLofiStream();
            return;
        }

        for (Transaction txn : ctx.getPendingBacklog()) {
            retryWithBackoff(() -> orchestrator.settle(txn), 3);
        }

        if (isOvertimeActive && ctx.clockHour() >= 21) {
            AppraisalDenialStrategy.promise("next cycle, definitely");
        }
    }
}`;

export const TERMINAL_LINES = [
  { text: '$ ./gradlew build --parallel', cls: '' },
  { text: '> Task :corporate-core:compileJava', cls: '' },
  { text: '> Task :corporate-core:test', cls: '' },
  { text: 'PaymentGatewayServiceTest > settlesBacklog() PASSED', cls: 'ok' },
  { text: 'ChaiBreakSchedulerTest > neverSkipsFivePm() PASSED', cls: 'ok' },
  { text: 'AppraisalTest > givesFairHike() SKIPPED (unrealistic)', cls: 'warn' },
  { text: 'BUILD SUCCESSFUL in 41s — 38 actionable tasks', cls: 'ok' },
  { text: '[TERMINAL] compilation successful. Watching for file changes…', cls: '' },
];

export const FAKE_FILES = [
  'PaymentGatewayService.java — CorporateCoreEngine',
  'ClientEscalationHandler.java — CorporateCoreEngine',
  'OvertimeCalculations.kt — CorporateCoreEngine',
];

export const CHAI_QUOTES = [
  'Chai pe chalte hain! ☕',
  '5 baje tapri pe milte hain 🫖',
  '"Let\'s take this offline" — every meeting ever',
  'Status green rakho, kaam apne aap ho jayega 🟢',
  'Monday blues ka ilaaj: Bollywood lo-fi 🎧',
  'Sprint planning = wishful thinking with a whiteboard',
];

export function shareTargets(url, title) {
  const u = encodeURIComponent(url);
  const t = encodeURIComponent(title);
  return [
    { label: '💬 WhatsApp', href: `https://wa.me/?text=${t}%20${u}` },
    { label: '✈️ Telegram', href: `https://t.me/share/url?url=${u}&text=${t}` },
    { label: '𝕏 Twitter', href: `https://twitter.com/intent/tweet?url=${u}&text=${t}` },
    { label: '💼 LinkedIn', href: `https://www.linkedin.com/sharing/share-offsite/?url=${u}` },
    { label: '🟠 Reddit', href: `https://www.reddit.com/submit?url=${u}&title=${t}` },
    { label: '✉️ Email', href: `mailto:?subject=${t}&body=${u}` },
  ];
}

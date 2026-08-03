import { useEffect } from "react";

import { FeatureGrid } from "../components/landing/FeatureGrid";
import { FinalCTA } from "../components/landing/FinalCTA";
import { Footer } from "../components/landing/Footer";
import { Hero } from "../components/landing/Hero";
import { LearningLoop } from "../components/landing/LearningLoop";
import { Navbar } from "../components/landing/Navbar";
import { RibbonsBackground } from "../components/landing/RibbonsBackground";
import { StudyHub } from "../components/landing/StudyHub";
import { TechStack } from "../components/landing/TechStack";

const DESCRIPTION =
  "Agentbook remembers what you learn, answers with citations, generates quizzes, and turns study evidence into practical next steps.";

export function LandingPage() {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = "Agentbook | Your AI Study Companion";

    let description = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    const previousDescription = description?.content;
    if (!description) {
      description = document.createElement("meta");
      description.name = "description";
      document.head.appendChild(description);
    }
    description.content = DESCRIPTION;

    return () => {
      document.title = previousTitle;
      if (description && previousDescription !== undefined) {
        description.content = previousDescription;
      }
    };
  }, []);

  return (
    <main className="landing-page relative min-h-[100dvh] overflow-x-hidden bg-background dark:bg-dark-bg">
      <Navbar />
      <RibbonsBackground />
      <Hero />
      <FeatureGrid />
      <LearningLoop />
      <StudyHub />
      <TechStack />
      <FinalCTA />
      <Footer />
    </main>
  );
}

export default LandingPage;

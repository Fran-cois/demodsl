import { Hero } from "@/components/Hero";
import { DemoVideo } from "@/components/DemoVideo";
import { Features } from "@/components/Features";
import { CodeExample } from "@/components/CodeExample";
import { Architecture } from "@/components/Architecture";
import { Install } from "@/components/Install";
import { Footer } from "@/components/Footer";

export default function Home() {
  return (
    <main className="min-h-screen">
      <Hero />
      <DemoVideo />
      <Install />
      <Features />
      <CodeExample />
      <Architecture />
      <Footer />
    </main>
  );
}

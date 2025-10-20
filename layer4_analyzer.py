"""
LAYER 4: AI Analysis & Insights
- Analyzes scraped product data using OpenAI GPT-5-nano
- Generates competitive analysis and keyword effectiveness reports
- Produces markdown reports with actionable insights
"""

import json
import logging
import openai
from pathlib import Path
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """AI-powered analysis of Amazon scraping results"""

    def __init__(self, openai_api_key: str):
        """
        Initialize AI analyzer with OpenAI API key

        Args:
            openai_api_key: OpenAI API key for GPT-5-nano
        """
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.model = "gpt-5-nano"
        logger.info("✓ Initialized AI Analyzer (GPT-5-nano)")

    def analyze_country_data(self, country: str, json_data: Dict) -> str:
        """
        Analyze scraped data for a single country using GPT-5-nano

        Args:
            country: Country code (e.g., 'uk', 'us')
            json_data: Parsed JSON data from all_keywords_*.json file

        Returns:
            Markdown-formatted analysis report
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"AI ANALYSIS: {country.upper()}")
        logger.info(f"{'='*70}")

        # Prepare data summary for GPT
        data_summary = self._prepare_data_summary(json_data)

        # Create prompt for GPT-5-nano
        prompt = f"""You are an expert Amazon marketplace analyst. Analyze the following product data and provide insights.

**Market**: {country.upper()}
**Keywords Analyzed**: {len(json_data)} keywords
**Data Summary**:
{data_summary}

Please provide a comprehensive analysis covering:

1. **KEYWORD EFFECTIVENESS ANALYSIS**
   - Which keywords perform best (most products, best BSR rankings)?
   - Which keywords underperform or have low product counts?
   - Keyword recommendations (keep, modify, or remove)

2. **COMPETITIVE LANDSCAPE ANALYSIS**
   - Top competing products (by BSR, review count, rating)
   - Price range analysis and competitive pricing insights
   - Market saturation indicators (how many products per keyword)
   - Product differentiation opportunities

3. **MARKET INSIGHTS**
   - Average ratings and review counts
   - BSR category dominance (which categories are most common)
   - Pricing trends and sweet spots
   - Badge prevalence ("Amazon's Choice", "Best Seller", etc.)

4. **ACTIONABLE RECOMMENDATIONS**
   - Product positioning strategies
   - Pricing recommendations
   - Keyword optimization suggestions
   - Market entry opportunities

Format your response in clean markdown with headers, bullet points, and tables where appropriate.
Be specific with data points (ASINs, numbers, percentages).
"""

        try:
            logger.info("  Sending data to GPT-5-nano...")
            logger.info(f"  Input prompt length: {len(prompt)} characters")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert Amazon marketplace analyst specializing in competitive intelligence and keyword optimization."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=16000  # GPT-5-nano needs room for reasoning + output
            )

            analysis = response.choices[0].message.content
            logger.info(f"  ✓ Response received: {len(analysis) if analysis else 0} characters")

            # Debug: Check if response is empty
            if not analysis or len(analysis.strip()) == 0:
                logger.warning("  ⚠ GPT returned empty response!")
                logger.info(f"  Response object: {response}")
                return f"# Analysis Failed\n\nGPT-5-nano returned an empty response. This might be due to model limitations."

            logger.info(f"  ✓ Generated {len(analysis)} character analysis")
            return analysis

        except Exception as e:
            logger.error(f"  ✗ AI Analysis failed: {e}")
            return f"# Analysis Failed\n\nError: {str(e)}"

    def _prepare_data_summary(self, json_data: List[Dict]) -> str:
        """
        Prepare a concise summary of JSON data for GPT analysis

        Args:
            json_data: List of keyword results

        Returns:
            Formatted string summary
        """
        summary_lines = []

        for keyword_result in json_data:
            keyword = keyword_result.get('keyword', 'Unknown')
            status = keyword_result.get('status', 'unknown')
            products = keyword_result.get('products', [])

            if status != 'success' or not products:
                summary_lines.append(f"\n**Keyword: {keyword}**")
                summary_lines.append(f"- Status: FAILED or NO PRODUCTS")
                continue

            # Calculate metrics
            prices = [p.get('price', 'N/A') for p in products if p.get('price') not in ['[REPEATED]', None]]
            ratings = [p.get('rating') for p in products if p.get('rating') not in ['[REPEATED]', None] and p.get('rating')]
            review_counts = [p.get('review_count') for p in products if p.get('review_count') not in ['[REPEATED]', None] and p.get('review_count')]
            bsr_ranks = [p.get('bsr_rank') for p in products if p.get('bsr_rank') and p.get('bsr_rank') != '[REPEATED]']

            avg_rating = sum(ratings) / len(ratings) if ratings else 0
            avg_reviews = sum(review_counts) / len(review_counts) if review_counts else 0
            min_bsr = min(bsr_ranks) if bsr_ranks else None

            # Get top 3 products by BSR
            products_with_bsr = [p for p in products if p.get('bsr_rank') and isinstance(p.get('bsr_rank'), int)]
            top_products = sorted(products_with_bsr, key=lambda x: x['bsr_rank'])[:3]

            summary_lines.append(f"\n**Keyword: {keyword}**")
            summary_lines.append(f"- Total Products: {len(products)}")
            summary_lines.append(f"- Avg Rating: {avg_rating:.2f}/5" if avg_rating else "- Avg Rating: N/A")
            summary_lines.append(f"- Avg Reviews: {int(avg_reviews)}" if avg_reviews else "- Avg Reviews: N/A")
            summary_lines.append(f"- Best BSR: #{min_bsr:,}" if min_bsr else "- Best BSR: N/A")
            summary_lines.append(f"- Price Range: {prices[0]} - {prices[-1]}" if len(prices) >= 2 else f"- Prices: {', '.join(map(str, prices[:3]))}")

            if top_products:
                summary_lines.append("- Top 3 Products:")
                for i, p in enumerate(top_products, 1):
                    asin = p.get('asin', 'N/A')
                    bsr = p.get('bsr_rank', 0)
                    price = p.get('price', 'N/A')
                    rating = p.get('rating', 'N/A')
                    reviews = p.get('review_count', 0)
                    title_short = p.get('title', 'N/A')[:50] + '...' if len(p.get('title', '')) > 50 else p.get('title', 'N/A')

                    # Format BSR and reviews with commas only if they're numbers
                    bsr_str = f"{bsr:,}" if isinstance(bsr, int) else str(bsr)
                    reviews_str = f"{reviews:,}" if isinstance(reviews, int) else str(reviews)

                    summary_lines.append(f"  {i}. {asin} | BSR: {bsr_str} | {price} | ★{rating} ({reviews_str} reviews)")
                    summary_lines.append(f"     Title: {title_short}")

        return '\n'.join(summary_lines)

    def generate_multi_country_report(self, output_dir: Path, countries: List[str]) -> str:
        """
        Generate AI analysis reports for all countries

        Args:
            output_dir: Base output directory containing country subdirectories
            countries: List of country codes to analyze

        Returns:
            Path to the generated consolidated report
        """
        logger.info(f"\n{'*'*70}")
        logger.info(f"GENERATING AI ANALYSIS REPORTS")
        logger.info(f"{'*'*70}\n")

        all_analyses = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        for country in countries:
            country_dir = output_dir / country

            # Find the most recent all_keywords_*.json file
            json_files = sorted(country_dir.glob('all_keywords_*.json'), reverse=True)

            if not json_files:
                logger.warning(f"  ⚠ No data files found for {country.upper()}")
                continue

            latest_file = json_files[0]
            logger.info(f"  Analyzing: {latest_file.name}")

            # Load JSON data
            with open(latest_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            # Generate analysis
            analysis = self.analyze_country_data(country, json_data)

            # Save individual country report
            report_file = country_dir / f"ai_analysis_{timestamp}.md"
            country_report = f"""# AI Market Analysis - {country.upper()}

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Model**: GPT-5-nano
**Data Source**: {latest_file.name}

---

{analysis}

---

*Analysis generated by Layer 4 AI Analyzer using OpenAI GPT-5-nano*
"""

            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(country_report)

            logger.info(f"  ✓ Saved: {report_file.name}\n")

            all_analyses.append({
                'country': country.upper(),
                'analysis': analysis
            })

        # Generate consolidated report
        consolidated_report = self._create_consolidated_report(all_analyses, timestamp)
        consolidated_file = output_dir / f"ai_analysis_all_countries_{timestamp}.md"

        with open(consolidated_file, 'w', encoding='utf-8') as f:
            f.write(consolidated_report)

        logger.info(f"{'='*70}")
        logger.info(f"✓ AI ANALYSIS COMPLETE")
        logger.info(f"  Individual reports: {len(all_analyses)} countries")
        logger.info(f"  Consolidated report: {consolidated_file.name}")
        logger.info(f"{'='*70}\n")

        return str(consolidated_file)

    def _create_consolidated_report(self, analyses: List[Dict], timestamp: str) -> str:
        """
        Create a consolidated report from all country analyses

        Args:
            analyses: List of analysis dictionaries
            timestamp: Timestamp string

        Returns:
            Consolidated markdown report
        """
        report_parts = [
            f"# Multi-Country Amazon Market Analysis",
            f"",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Model**: GPT-5-nano",
            f"**Markets Analyzed**: {len(analyses)}",
            f"",
            f"---",
            f""
        ]

        for analysis_data in analyses:
            report_parts.append(f"## {analysis_data['country']} Market")
            report_parts.append("")
            report_parts.append(analysis_data['analysis'])
            report_parts.append("")
            report_parts.append("---")
            report_parts.append("")

        report_parts.append("*Multi-country analysis generated by Layer 4 AI Analyzer using OpenAI GPT-5-nano*")

        return '\n'.join(report_parts)


def main():
    """Standalone test entry point"""
    import sys

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Load config
    with open('config.json') as f:
        config = json.load(f)

    openai_key = config['api_keys'].get('openai')
    if not openai_key:
        logger.error("OpenAI API key not found in config.json")
        sys.exit(1)

    countries = config['settings'].get('countries', ['uk'])
    output_dir = Path(config['settings']['output_dir'])

    # Run analysis
    analyzer = AIAnalyzer(openai_key)
    report_path = analyzer.generate_multi_country_report(output_dir, countries)

    print(f"\n✓ Analysis complete! Report: {report_path}")


if __name__ == '__main__':
    main()

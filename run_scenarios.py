#!/usr/bin/env python3
"""Run evaluation scenarios with flexible filtering.

Usage:
    # Run all scenarios
    python3 run_scenarios.py
    
    # Run specific category
    python3 run_scenarios.py --category monitoring
    
    # Run specific scenario file
    python3 run_scenarios.py --scenario cpu_memory.yaml
    
    # Run with custom config
    python3 run_scenarios.py --system-config eval/system.yaml.local
"""

import subprocess
import sys
import csv
import json
import re
from pathlib import Path
from datetime import datetime
import argparse


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print a formatted header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_success(text):
    """Print success message."""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message."""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message."""
    print(f"{Colors.OKCYAN}{text}{Colors.ENDC}")


def run_scenario(scenario_file, system_config, output_base):
    """Run a single scenario evaluation.
    
    Args:
        scenario_file: Path to the scenario YAML file
        system_config: Path to system configuration file
        output_base: Base directory for outputs
        
    Returns:
        dict: Results including scenario name, success status, and output directory
    """
    # Ensure scenario_file is a Path object
    scenario_file = Path(scenario_file)
    
    # Create output directory per scenario
    scenario_name = scenario_file.stem
    category = scenario_file.parent.name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_base / category / f"{scenario_name}_{timestamp}"
    
    # Get relative path for display
    try:
        display_path = scenario_file.relative_to(Path.cwd())
    except ValueError:
        display_path = scenario_file
    
    print_header(f"🚀 Running: {display_path}")
    
    print_info(f"Category: {category}")
    print_info(f"Scenario: {scenario_name}")
    
    # Get relative path for output directory
    try:
        display_output = output_dir.relative_to(Path.cwd())
    except ValueError:
        display_output = output_dir
    
    print_info(f"Output: {display_output}\n")
    
    # Find lightspeed-evaluation directory
    lightspeed_dir = Path.cwd().parent / "lightspeed-evaluation"
    if not lightspeed_dir.exists():
        lightspeed_dir = Path.home() / "Documents" / "lightspeed-evaluation"
    
    if not lightspeed_dir.exists():
        print_error(f"lightspeed-evaluation directory not found!")
        print_info("Expected at: ../lightspeed-evaluation or ~/Documents/lightspeed-evaluation")
        return {
            "scenario": scenario_file.name,
            "category": category,
            "success": False,
            "output_dir": output_dir
        }
    
    # Convert paths to absolute for cross-directory execution
    abs_system_config = Path(system_config).resolve()
    abs_scenario_file = Path(scenario_file).resolve()
    abs_output_dir = Path(output_dir).resolve()
    
    cmd = [
        "uv", "run", "lightspeed-eval",
        "--system-config", str(abs_system_config),
        "--eval-data", str(abs_scenario_file),
        "--output-dir", str(abs_output_dir)
    ]
    
    # Run from lightspeed-evaluation directory
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(lightspeed_dir))
    
    success = result.returncode == 0
    
    # Extract statistics from output
    stats = {}
    if success and result.stdout:
        # Parse output for statistics
        conversations_match = re.search(r'Evaluation data loaded: (\d+) conversations', result.stdout)
        total_match = re.search(r'(\d+) evaluations completed', result.stdout)
        pass_match = re.search(r'Pass: (\d+)', result.stdout)
        fail_match = re.search(r'Fail: (\d+)', result.stdout)
        
        if conversations_match:
            stats["conversations"] = int(conversations_match.group(1))
        if total_match:
            stats["total_evals"] = int(total_match.group(1))
        if pass_match:
            stats["passed"] = int(pass_match.group(1))
        if fail_match:
            stats["failed"] = int(fail_match.group(1))
        
        # Print output
        print(result.stdout)
    elif result.stderr:
        print(result.stderr)
    
    if success:
        print_success(f"Completed: {scenario_name}")
    else:
        print_error(f"Failed: {scenario_name}")
    
    return {
        "scenario": scenario_file.name,
        "category": category,
        "success": success,
        "output_dir": output_dir,
        "stats": stats
    }


def merge_csv_files(output_base, timestamp):
    """Merge all scenario CSV files into one consolidated CSV."""
    all_rows = []
    header = None
    
    # Find all detailed CSV files
    for csv_file in output_base.rglob("*_detailed.csv"):
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            if header is None:
                header = reader.fieldnames
            for row in reader:
                all_rows.append(row)
    
    if not all_rows:
        return None
    
    # Write consolidated CSV
    output_file = output_base / f"consolidated_{timestamp}_detailed.csv"
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(all_rows)
    
    return output_file


def merge_json_files(output_base, timestamp):
    """Merge all scenario JSON files into one consolidated JSON."""
    consolidated = {
        "timestamp": datetime.now().isoformat(),
        "total_evaluations": 0,
        "total_scenarios": 0,
        "summary_stats": {
            "overall": {
                "TOTAL": 0,
                "PASS": 0,
                "FAIL": 0,
                "ERROR": 0,
                "SKIPPED": 0
            },
            "by_metric": {},
            "by_scenario": []
        }
    }
    
    # Find all summary JSON files
    for json_file in output_base.rglob("*_summary.json"):
        with open(json_file, 'r') as f:
            data = json.load(f)
            
            # Aggregate overall stats
            summary_stats = data.get("summary_stats", {})
            overall = summary_stats.get("overall", {})
            
            consolidated["summary_stats"]["overall"]["TOTAL"] += overall.get("TOTAL", 0)
            consolidated["summary_stats"]["overall"]["PASS"] += overall.get("PASS", 0)
            consolidated["summary_stats"]["overall"]["FAIL"] += overall.get("FAIL", 0)
            consolidated["summary_stats"]["overall"]["ERROR"] += overall.get("ERROR", 0)
            consolidated["summary_stats"]["overall"]["SKIPPED"] += overall.get("SKIPPED", 0)
            
            # Aggregate by metric
            for metric_name, metric_stats in summary_stats.get("by_metric", {}).items():
                if metric_name not in consolidated["summary_stats"]["by_metric"]:
                    consolidated["summary_stats"]["by_metric"][metric_name] = {
                        "pass": 0,
                        "fail": 0,
                        "error": 0,
                        "skipped": 0,
                        "scores": []
                    }
                
                consolidated["summary_stats"]["by_metric"][metric_name]["pass"] += metric_stats.get("pass", 0)
                consolidated["summary_stats"]["by_metric"][metric_name]["fail"] += metric_stats.get("fail", 0)
                consolidated["summary_stats"]["by_metric"][metric_name]["error"] += metric_stats.get("error", 0)
                consolidated["summary_stats"]["by_metric"][metric_name]["skipped"] += metric_stats.get("skipped", 0)
                
                if "scores" in metric_stats:
                    consolidated["summary_stats"]["by_metric"][metric_name]["scores"].extend(metric_stats["scores"])
            
            # Store scenario info
            # Strip timestamp suffix (format: _YYYYMMDD_HHMMSS)
            scenario_name = re.sub(r'_\d{8}_\d{6}$', '', json_file.parent.name)
            category_name = json_file.parent.parent.name
            
            consolidated["summary_stats"]["by_scenario"].append({
                "scenario": f"{category_name}/{scenario_name}",
                "pass": overall.get("PASS", 0),
                "fail": overall.get("FAIL", 0),
                "total": overall.get("TOTAL", 0)
            })
            
            consolidated["total_scenarios"] += 1
    
    consolidated["total_evaluations"] = consolidated["summary_stats"]["overall"]["TOTAL"]
    
    # Calculate pass rates
    total = consolidated["summary_stats"]["overall"]["TOTAL"]
    if total > 0:
        consolidated["summary_stats"]["overall"]["pass_rate"] = (
            consolidated["summary_stats"]["overall"]["PASS"] / total * 100
        )
        consolidated["summary_stats"]["overall"]["fail_rate"] = (
            consolidated["summary_stats"]["overall"]["FAIL"] / total * 100
        )
    
    # Write consolidated JSON
    output_file = output_base / f"consolidated_{timestamp}_summary.json"
    with open(output_file, 'w') as f:
        json.dump(consolidated, f, indent=2)
    
    return output_file


def generate_txt_summary(output_base, timestamp, json_file):
    """Generate consolidated TXT summary from JSON data (LightSpeed format)."""
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    output_file = output_base / f"consolidated_{timestamp}_summary.txt"
    
    with open(output_file, 'w') as f:
        # Match LightSpeed framework format
        f.write("LSC Evaluation Framework - Summary Report\n")
        f.write("=" * 50 + "\n\n")
        
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Evaluations: {data['total_evaluations']}\n\n")
        
        overall = data["summary_stats"]["overall"]
        f.write("Overall Statistics:\n")
        f.write("-" * 20 + "\n")
        f.write(f"Pass: {overall['PASS']} ({overall.get('pass_rate', 0):.1f}%)\n")
        f.write(f"Fail: {overall['FAIL']} ({overall.get('fail_rate', 0):.1f}%)\n")
        f.write(f"Error: {overall['ERROR']} ({overall.get('error_rate', 0):.1f}%)\n")
        f.write(f"Skipped: {overall['SKIPPED']} ({overall.get('skipped_rate', 0):.1f}%)\n\n")
        
        # Metrics breakdown
        f.write("Results by Metric:\n")
        f.write("-" * 20 + "\n")
        for metric_name, stats in data["summary_stats"]["by_metric"].items():
            total_metric = stats["pass"] + stats["fail"]
            pass_rate = (stats["pass"] / total_metric * 100) if total_metric > 0 else 0
            f.write(f"\n{metric_name}:\n")
            f.write(f"  Total: {total_metric}\n")
            f.write(f"  Pass: {stats['pass']} ({pass_rate:.1f}%)\n")
            f.write(f"  Fail: {stats['fail']}\n")
        
        # Scenario breakdown (additional info not in single YAML version)
        f.write("\n" + "=" * 50 + "\n")
        f.write("Results by Scenario:\n")
        f.write("-" * 20 + "\n")
        for scenario in data["summary_stats"]["by_scenario"]:
            pass_rate = (scenario["pass"] / scenario["total"] * 100) if scenario["total"] > 0 else 0
            f.write(f"\n{scenario['scenario']}:\n")
            f.write(f"  Total: {scenario['total']}\n")
            f.write(f"  Pass: {scenario['pass']} ({pass_rate:.1f}%)\n")
            f.write(f"  Fail: {scenario['fail']}\n")
        
        f.write("\n" + "=" * 50 + "\n")
    
    return output_file


def main():
    """Main entry point for the scenario runner."""
    parser = argparse.ArgumentParser(
        description="Run evaluation scenarios with flexible filtering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all scenarios
  python3 run_scenarios.py
  
  # Run only monitoring scenarios
  python3 run_scenarios.py --category monitoring
  
  # Run only troubleshooting scenarios
  python3 run_scenarios.py --category troubleshooting
  
  # Run specific scenario file
  python3 run_scenarios.py --scenario cpu_memory.yaml
  
  # Run with custom config
  python3 run_scenarios.py --system-config eval/system.yaml.local
        """
    )
    
    parser.add_argument(
        "--category",
        help="Run specific category (e.g., 'monitoring', 'troubleshooting')",
        default=None
    )
    parser.add_argument(
        "--scenario",
        help="Run specific scenario file (e.g., 'cpu_memory.yaml')",
        default=None
    )
    parser.add_argument(
        "--system-config",
        default="eval/system.yaml.local",
        help="System config file (default: eval/system.yaml.local)"
    )
    parser.add_argument(
        "--output-dir",
        default="eval/output",
        help="Base output directory (default: eval/output)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available scenarios without running"
    )
    
    args = parser.parse_args()
    
    scenarios_dir = Path("eval/scenarios")
    system_config = Path(args.system_config)
    output_base = Path(args.output_dir)
    
    # Check if system config exists
    if not system_config.exists():
        print_error(f"System config not found: {system_config}")
        print_info("Create eval/system.yaml.local or use --system-config flag")
        return 1
    
    # Find scenario files
    if args.scenario:
        # Run specific scenario
        scenario_files = list(scenarios_dir.rglob(args.scenario))
        if not scenario_files:
            print_error(f"Scenario not found: {args.scenario}")
            return 1
    elif args.category:
        # Run all scenarios in a category
        category_dir = scenarios_dir / args.category
        if not category_dir.exists():
            print_error(f"Category not found: {args.category}")
            print_info(f"Available categories: {', '.join([d.name for d in scenarios_dir.iterdir() if d.is_dir()])}")
            return 1
        scenario_files = sorted(category_dir.rglob("*.yaml"))
    else:
        # Run all scenarios
        scenario_files = sorted(scenarios_dir.rglob("*.yaml"))
    
    if not scenario_files:
        print_error("No scenarios found!")
        return 1
    
    # List scenarios if requested
    if args.list:
        print_header("📋 Available Scenarios")
        categories = {}
        for f in scenario_files:
            category = f.parent.name
            if category not in categories:
                categories[category] = []
            categories[category].append(f.stem)
        
        for category, scenarios in sorted(categories.items()):
            print(f"\n{Colors.BOLD}{category}:{Colors.ENDC}")
            for scenario in sorted(scenarios):
                print(f"  • {scenario}.yaml")
        
        print(f"\n{Colors.BOLD}Total: {len(scenario_files)} scenario(s){Colors.ENDC}")
        return 0
    
    # Show what will run
    print_header("📋 Scenarios to Run")
    
    categories = {}
    for f in scenario_files:
        category = f.parent.name
        if category not in categories:
            categories[category] = []
        categories[category].append(f.stem)
    
    for category, scenarios in sorted(categories.items()):
        print(f"{Colors.BOLD}{category}:{Colors.ENDC}")
        for scenario in sorted(scenarios):
            print(f"  • {scenario}.yaml")
    
    print(f"\n{Colors.BOLD}Total: {len(scenario_files)} scenario(s){Colors.ENDC}")
    print(f"System config: {system_config}")
    print(f"Output base: {output_base}\n")
    
    # Run scenarios
    results = []
    for idx, scenario_file in enumerate(scenario_files, 1):
        print(f"\n{Colors.BOLD}[{idx}/{len(scenario_files)}]{Colors.ENDC}")
        result = run_scenario(scenario_file, system_config, output_base)
        results.append(result)
    
    # Summary
    print_header("📊 EVALUATION SUMMARY")
    
    scenario_passed = sum(1 for r in results if r["success"])
    scenario_failed = len(results) - scenario_passed
    
    # Calculate total tests and evaluations from results
    total_tests = 0
    total_evaluations = 0
    eval_passed = 0
    eval_failed = 0
    
    for r in results:
        if r["success"] and "stats" in r:
            total_tests += r["stats"]["conversations"]
            total_evaluations += r["stats"]["total_evals"]
            eval_passed += r["stats"]["passed"]
            eval_failed += r["stats"]["failed"]
    
    print(f"{Colors.BOLD}Scenario Files:{Colors.ENDC} {len(results)}")
    print(f"{Colors.BOLD}Test Cases (Conversations):{Colors.ENDC} {total_tests}")
    print(f"{Colors.BOLD}Total Evaluations:{Colors.ENDC} {total_evaluations}")
    print()
    
    if total_evaluations > 0:
        pass_pct = eval_passed / total_evaluations * 100
        print_success(f"Pass: {eval_passed} ({pass_pct:.1f}%)")
        if eval_failed > 0:
            print_error(f"Fail: {eval_failed}")
        else:
            print(f"{Colors.OKGREEN}Fail: 0{Colors.ENDC}")
    else:
        print_info("No evaluation results to display")
    
    if scenario_failed > 0:
        print(f"\n{Colors.BOLD}Failed scenario files:{Colors.ENDC}")
        for r in results:
            if not r["success"]:
                print(f"  • {r['category']}/{r['scenario']}")
    
    # Get relative path for summary output
    try:
        display_output_base = output_base.relative_to(Path.cwd())
    except ValueError:
        display_output_base = output_base
    
    print(f"\n{Colors.BOLD}Output directory:{Colors.ENDC} {display_output_base}")
    
    # Generate consolidated reports
    print(f"\n{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}📄 Generating Consolidated Reports{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 70}{Colors.ENDC}\n")
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Merge CSV files
        csv_file = merge_csv_files(output_base, timestamp)
        if csv_file:
            try:
                display_path = csv_file.relative_to(Path.cwd())
            except ValueError:
                display_path = csv_file
            print_success(f"CSV:  {display_path}")
        
        # Merge JSON files
        json_file = merge_json_files(output_base, timestamp)
        if json_file:
            try:
                display_path = json_file.relative_to(Path.cwd())
            except ValueError:
                display_path = json_file
            print_success(f"JSON: {display_path}")
            
            # Generate TXT summary from JSON
            txt_file = generate_txt_summary(output_base, timestamp, json_file)
            if txt_file:
                try:
                    display_path = txt_file.relative_to(Path.cwd())
                except ValueError:
                    display_path = txt_file
                print_success(f"TXT:  {display_path}")
        
        print()
        print_info("Consolidated reports generated successfully")
        
    except Exception as e:
        print(f"{Colors.WARNING}Could not generate consolidated reports: {e}{Colors.ENDC}")
    
    return 0 if eval_failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print_info("\n\nInterrupted by user")
        sys.exit(130)

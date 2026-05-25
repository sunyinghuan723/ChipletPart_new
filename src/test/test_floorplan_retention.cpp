#include "floorplan.h"

#include <iostream>
#include <memory>
#include <vector>

namespace {

std::unique_ptr<SACore> BuildCore(unsigned seed, bool retain_best_feasible) {
  std::vector<Chiplet> chiplets = {
      Chiplet(0.0f, 0.0f, 1.0f, 1.0f, 1.0f, 0.0f),
      Chiplet(0.0f, 0.0f, 1.0f, 1.0f, 1.0f, 0.0f),
      Chiplet(0.0f, 0.0f, 1.0f, 1.0f, 1.0f, 0.0f),
  };
  std::vector<BundledNet> nets = {
      BundledNet({0, 1}, 1, 0.01f, 0.0f),
  };
  auto core = std::make_unique<SACore>(
      0, chiplets, nets,
      0.0f, 0.0f, 0.0f,
      0.5f, 0.5f, 0.0f, 0.0f, 0.0f,
      1, 12, 0.95f, seed);
  core->setRetainBestFeasible(retain_best_feasible);
  return core;
}

}  // namespace

int main() {
  bool saw_invalid_annealing_endpoint = false;
  for (unsigned seed = 0; seed < 128; ++seed) {
    auto ordinary = BuildCore(seed, false);
    ordinary->run();
    if (ordinary->isValid()) {
      continue;
    }

    saw_invalid_annealing_endpoint = true;
    auto retained = BuildCore(seed, true);
    retained->run();
    if (!retained->isValid()) {
      std::cerr << "retained final-validation run lost a feasible floorplan"
                << std::endl;
      return 1;
    }
    break;
  }

  if (!saw_invalid_annealing_endpoint) {
    std::cerr << "test setup did not produce an invalid annealing endpoint"
              << std::endl;
    return 1;
  }
  return 0;
}

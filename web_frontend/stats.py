class IncrementalStats:
    """Class for calculating mean and standard deviation incrementally; ensures not having to load all results into memory"""
    def __init__(self):
        self.n = 0

    def add(self, x):
        x = float(x)
        self.n += 1
        if self.n == 1:
            self.mean = x
            self.variance = 0.0
        else:
            #Algorithm for incremental mean and variance by B. P. Welford, Technometrics, Vol. 4, No. 3 (Aug., 1962), pp. 419-420

            last_mean = self.mean
            last_variance = self.variance
            
            self.mean = last_mean + ((x - last_mean) / self.n)
            self.variance = last_variance + ((x - last_mean)*(x - self.mean))
            
    def get_mean(self):
        return self.mean
        
    def get_variance(self):
        if self.n > 1:
            return self.variance / (self.n - 1)
        else:
            return 0.0
        
    def get_stdev(self):
        import math
        return math.sqrt(self.get_variance())
